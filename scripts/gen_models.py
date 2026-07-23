"""Genera il blocco JS `MODELS` in docs/index.html da config/models.yaml.

`config/models.yaml` è l'unica fonte del registro modelli (id, label, pricing,
search/chat). Il sito statico ha una copia inline di quel registro: questo script
la rigenera in modo deterministico tra i marker MODELS:GEN, così non va mai
allineata a mano.

Uso:
    python -m scripts.gen_models          # riscrive il blocco
    python -m scripts.gen_models --check   # esce !=0 se il blocco è disallineato
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODELS_YAML = ROOT / "config" / "models.yaml"
INDEX_HTML = ROOT / "docs" / "index.html"

START = "/* MODELS:GEN:START */"
END = "/* MODELS:GEN:END */"


def _num(x) -> str:
    """Formatta un prezzo come numero JS stabile (1.0, 0.005, 15.0)."""
    return json.dumps(float(x if x is not None else 0))


def build_block() -> str:
    models = yaml.safe_load(MODELS_YAML.read_text(encoding="utf-8")) or []
    lines = [START, "const MODELS = {"]
    for m in models:
        mid = m["id"]
        label = json.dumps(m.get("label") or mid, ensure_ascii=False)
        mtype = "search" if m.get("web_search") else "chat"
        lines.append(
            f'  {json.dumps(mid)}: {{label: {label}, type: "{mtype}", '
            f'in: {_num(m.get("input_price_per_1m"))}, '
            f'out: {_num(m.get("output_price_per_1m"))}, '
            f'web: {_num(m.get("web_search_price"))}}},'
        )
    lines.append("};")
    lines.append(END)
    return "\n".join(lines)


def _splice(html: str, block: str) -> str:
    i, j = html.index(START), html.index(END) + len(END)
    return html[:i] + block + html[j:]


def main() -> None:
    check = "--check" in sys.argv
    html = INDEX_HTML.read_text(encoding="utf-8")
    if START not in html or END not in html:
        raise SystemExit(f"Marker MODELS:GEN non trovati in {INDEX_HTML}")
    new_html = _splice(html, build_block())
    if check:
        if new_html != html:
            raise SystemExit(
                "docs/index.html è disallineato da config/models.yaml — "
                "rigenera con `python -m scripts.gen_models`."
            )
        print("✓ MODELS in docs/index.html allineato a config/models.yaml")
        return
    if new_html != html:
        INDEX_HTML.write_text(new_html, encoding="utf-8")
        print(f"✓ Blocco MODELS rigenerato in {INDEX_HTML.relative_to(ROOT)}")
    else:
        print("✓ Nessuna modifica: già allineato")


if __name__ == "__main__":
    main()
