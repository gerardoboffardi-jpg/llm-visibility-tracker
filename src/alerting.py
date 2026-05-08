"""Alerting su Slack via webhook.

Logica:
- Confronta KPI della run più recente con la media delle ultime N run precedenti
- Allerta se citation_rate scende oltre `drop_threshold` (default 10 punti %)
- Allerta se compaiono nuovi domini competitor citati frequentemente
- Allerta se un prompt prima coperto da citazione target ora non lo è più

Configurazione (via env):
- SLACK_WEBHOOK_URL: URL del webhook Slack (Incoming Webhooks)
- ALERT_DROP_THRESHOLD: float (default 0.10 = 10pt percentuali)
- ALERT_BASELINE_RUNS: int (default 3)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

import requests
from sqlalchemy import func, select

from src.storage import Citation, Response, Run, get_session

logger = logging.getLogger(__name__)

DEFAULT_DROP_THRESHOLD = 0.10
DEFAULT_BASELINE_RUNS = 3


@dataclass
class Alert:
    severity: str    # "warning" | "critical" | "info"
    title: str
    message: str

    def slack_block(self) -> dict:
        emoji = {"critical": ":rotating_light:", "warning": ":warning:", "info": ":information_source:"}[self.severity]
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{self.title}*\n{self.message}",
            },
        }


@dataclass
class AlertReport:
    run_id: int
    alerts: list[Alert] = field(default_factory=list)
    current_citation_rate: float = 0.0
    baseline_citation_rate: float = 0.0

    @property
    def has_alerts(self) -> bool:
        return len(self.alerts) > 0


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _run_kpis(session, run_id: int) -> dict:
    """Calcola citation rate / mention rate / # citazioni di un run."""
    n_resp = session.scalar(
        select(func.count(Response.id)).where(Response.run_id == run_id)
    ) or 0
    if n_resp == 0:
        return {"n_resp": 0, "citation_rate": 0.0, "mention_rate": 0.0}
    n_cit = session.scalar(
        select(func.count(Response.id)).where(
            Response.run_id == run_id,
            Response.has_target_citation.is_(True),
        )
    ) or 0
    n_men = session.scalar(
        select(func.count(Response.id)).where(
            Response.run_id == run_id,
            Response.has_target_mention.is_(True),
        )
    ) or 0
    return {
        "n_resp": n_resp,
        "citation_rate": n_cit / n_resp,
        "mention_rate": n_men / n_resp,
    }


def _competitor_domains_this_run(session, run_id: int) -> set[str]:
    """Domini competitor citati in questo run."""
    rows = session.execute(
        select(Citation.domain)
        .join(Response, Response.id == Citation.response_id)
        .where(Response.run_id == run_id, Citation.is_competitor_domain.is_(True))
        .distinct()
    ).all()
    return {r[0] for r in rows}


def _competitor_domains_baseline(session, baseline_run_ids: list[int]) -> set[str]:
    if not baseline_run_ids:
        return set()
    rows = session.execute(
        select(Citation.domain)
        .join(Response, Response.id == Citation.response_id)
        .where(Response.run_id.in_(baseline_run_ids), Citation.is_competitor_domain.is_(True))
        .distinct()
    ).all()
    return {r[0] for r in rows}


def detect_alerts(
    run_id: int,
    *,
    drop_threshold: float = DEFAULT_DROP_THRESHOLD,
    baseline_runs: int = DEFAULT_BASELINE_RUNS,
) -> AlertReport:
    """Calcola gli alert per un run, confrontando con la baseline."""
    report = AlertReport(run_id=run_id)
    with get_session() as s:
        run = s.get(Run, run_id)
        if run is None:
            return report

        # Run precedenti (escluso il corrente), ordinato per data desc
        prev_run_ids = [
            r[0] for r in s.execute(
                select(Run.id).where(Run.id < run_id).order_by(Run.id.desc()).limit(baseline_runs)
            ).all()
        ]

        current = _run_kpis(s, run_id)
        report.current_citation_rate = current["citation_rate"]

        if not prev_run_ids:
            report.alerts.append(Alert(
                severity="info",
                title=f"Prima run registrata (#{run_id})",
                message=f"Citation rate iniziale: *{current['citation_rate']:.1%}* "
                        f"su {current['n_resp']} risposte.",
            ))
            return report

        baseline_kpis = [_run_kpis(s, rid) for rid in prev_run_ids]
        valid = [k for k in baseline_kpis if k["n_resp"] > 0]
        if not valid:
            return report

        baseline_cit = sum(k["citation_rate"] for k in valid) / len(valid)
        report.baseline_citation_rate = baseline_cit
        delta = current["citation_rate"] - baseline_cit

        # 1) Drop di citation rate
        if delta <= -drop_threshold:
            report.alerts.append(Alert(
                severity="critical",
                title="Citation rate in calo",
                message=(
                    f"Citation rate scesa da *{baseline_cit:.1%}* (media ultime "
                    f"{len(valid)} run) a *{current['citation_rate']:.1%}* "
                    f"({delta * 100:+.1f}pt)."
                ),
            ))
        elif delta >= drop_threshold:
            report.alerts.append(Alert(
                severity="info",
                title="Citation rate in crescita 🎉",
                message=(
                    f"Citation rate salita da {baseline_cit:.1%} a "
                    f"*{current['citation_rate']:.1%}* ({delta * 100:+.1f}pt)."
                ),
            ))

        # 2) Nuovi domini competitor
        new_domains = _competitor_domains_this_run(s, run_id) - _competitor_domains_baseline(s, prev_run_ids)
        if new_domains:
            report.alerts.append(Alert(
                severity="warning",
                title=f"Nuovi competitor citati ({len(new_domains)})",
                message="Domini comparsi per la prima volta: " +
                        ", ".join(f"`{d}`" for d in sorted(new_domains)),
            ))

    return report


# ---------------------------------------------------------------------------
# Slack delivery
# ---------------------------------------------------------------------------


def send_to_slack(report: AlertReport, *, webhook_url: str | None = None) -> bool:
    """Invia il report su Slack. Ritorna True se mandato, False se skip o errore."""
    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        logger.info("SLACK_WEBHOOK_URL non configurato — skip notifica")
        return False
    if not report.alerts:
        logger.info("Nessun alert — skip notifica")
        return False

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"LLM Visibility — Run #{report.run_id}",
            },
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"_Citation rate: *{report.current_citation_rate:.1%}* "
                        f"(baseline {report.baseline_citation_rate:.1%}) — "
                        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
            }],
        },
        {"type": "divider"},
    ]
    blocks.extend(a.slack_block() for a in report.alerts)

    try:
        r = requests.post(url, json={"blocks": blocks}, timeout=10)
        if r.status_code >= 300:
            logger.error("Slack webhook %s: %s", r.status_code, r.text[:300])
            return False
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("Slack send fallito: %s", e)
        return False
