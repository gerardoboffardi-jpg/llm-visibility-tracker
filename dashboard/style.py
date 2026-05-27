"""Stile globale per la dashboard Streamlit.

Applica una palette TAG (coral) + tipografia Poppins, card moderne con shadow
e tipografia ariosa ispirata a https://www.hubspot.com/products/aeo.

Uso:
    from dashboard.style import apply_style
    apply_style()  # subito dopo st.set_page_config
"""
from __future__ import annotations

import streamlit as st

# --- Palette TAG ----------------------------------------------------------
CORAL = "#E94E1B"
CORAL_DARK = "#C03E14"
CORAL_50 = "#FFF1EC"
CORAL_100 = "#FFE0D4"

NAVY = "#0F172A"
SLATE_700 = "#334155"
SLATE_500 = "#64748B"
SLATE_300 = "#CBD5E1"
SLATE_100 = "#F1F5F9"
SLATE_50 = "#F8FAFC"

GREEN = "#16A34A"
GREEN_50 = "#ECFDF5"
ORANGE = "#F97316"
ORANGE_50 = "#FFF7ED"
AMBER = "#F59E0B"
RED = "#DC2626"

# --- CSS globale ----------------------------------------------------------
_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"], .stMarkdown, .stText, .stTextInput, .stSelectbox,
.stButton, .stMetric, .stDataFrame, .stTabs, .stExpander, .stCaption,
.stRadio, .stCheckbox, .stForm, .stAlert {{
    font-family: 'Poppins', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif !important;
}}

/* Headings */
h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
    font-family: 'Poppins', system-ui, sans-serif !important;
    color: {NAVY};
    letter-spacing: -0.01em;
}}
h1 {{ font-weight: 700; }}
h2 {{ font-weight: 600; }}
h3 {{ font-weight: 600; }}

/* Background piu' pulito */
[data-testid="stAppViewContainer"] > .main {{
    background: {SLATE_50};
}}

/* ============ STATUS WIDGET CUSTOM (alto a destra) ============ */
/* Nasconde le icone SVG di sport di Streamlit (runner, ciclista, atleta in
   carrozzina, ecc) e le sostituisce con emoji animali + bandiere TAG-style.
   Il widget appare quando l'app sta processando (running state). */
[data-testid="stStatusWidget"] svg,
[data-testid="stStatusWidget"] [class*="RunningManIcon"],
[data-testid="stStatusWidget"] [class*="StRunningIcon"] {{
    display: none !important;
}}
[data-testid="stStatusWidget"] {{
    position: relative;
    min-width: 140px;
    padding-left: 36px !important;
}}
[data-testid="stStatusWidget"]::before {{
    content: "🦘";
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 1.3rem;
    line-height: 1;
    animation: tag-loader-bounce 0.9s infinite ease-in-out,
               tag-loader-cycle 4.5s infinite steps(1);
}}
@keyframes tag-loader-bounce {{
    0%, 100% {{ transform: translateY(-50%) scale(1); }}
    50%      {{ transform: translateY(calc(-50% - 4px)) scale(1.1); }}
}}
@keyframes tag-loader-cycle {{
    0%   {{ content: "🦘 🇮🇹"; }}
    11%  {{ content: "🐢 🇪🇺"; }}
    22%  {{ content: "🦊 🇫🇷"; }}
    33%  {{ content: "🦒 🇮🇹"; }}
    44%  {{ content: "🦋 🇪🇸"; }}
    55%  {{ content: "🦄 🇮🇪"; }}
    66%  {{ content: "🐧 🇸🇪"; }}
    77%  {{ content: "🦦 🇩🇰"; }}
    88%  {{ content: "🦢 🇨🇭"; }}
    100% {{ content: "🐨 🇮🇹"; }}
}}
[data-testid="stHeader"] {{
    background: transparent;
}}
.block-container {{
    padding-top: 2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1280px;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    background: white;
    border-right: 1px solid {SLATE_100};
}}
[data-testid="stSidebar"] .stMarkdown {{
    color: {SLATE_700};
}}

/* Metric (KPI nativi) */
[data-testid="stMetric"] {{
    background: white;
    border: 1px solid {SLATE_100};
    border-radius: 14px;
    padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
    transition: transform .12s ease, box-shadow .12s ease;
}}
[data-testid="stMetric"]:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(15,23,42,0.06);
}}
[data-testid="stMetricLabel"] {{
    color: {SLATE_500} !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600 !important;
}}
[data-testid="stMetricValue"] {{
    color: {NAVY} !important;
    font-weight: 700 !important;
    font-size: 1.9rem !important;
}}

/* Pulsanti */
.stButton > button {{
    border-radius: 10px;
    border: 1px solid {SLATE_100};
    background: white;
    color: {NAVY};
    font-weight: 500;
    transition: all .12s ease;
}}
.stButton > button:hover {{
    border-color: {CORAL};
    color: {CORAL};
}}
.stButton > button[kind="primary"] {{
    background: {CORAL};
    border-color: {CORAL};
    color: white;
}}
.stButton > button[kind="primary"]:hover {{
    background: {CORAL_DARK};
    border-color: {CORAL_DARK};
    color: white;
}}

/* DataFrame */
[data-testid="stDataFrame"] {{
    border: 1px solid {SLATE_100};
    border-radius: 12px;
    overflow: hidden;
    background: white;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    border-bottom: 1px solid {SLATE_100};
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent;
    border-radius: 8px 8px 0 0;
    padding: 10px 16px;
    font-weight: 500;
    color: {SLATE_500};
}}
.stTabs [aria-selected="true"] {{
    color: {CORAL} !important;
    background: white;
    border-bottom: 2px solid {CORAL};
}}

/* Expander */
.stExpander {{
    border: 1px solid {SLATE_100} !important;
    border-radius: 12px !important;
    background: white;
}}

/* Alert */
.stAlert {{
    border-radius: 12px;
    border: 1px solid transparent;
}}

/* Divider piu' soft */
hr {{
    border-color: {SLATE_100} !important;
    margin: 1.5rem 0 !important;
}}

/* Selectbox / inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {{
    border-radius: 10px !important;
}}

/* Link */
a {{
    color: {CORAL};
    text-decoration: none;
}}
a:hover {{
    color: {CORAL_DARK};
    text-decoration: underline;
}}

/* Custom componenti TAG */
.tag-hero {{
    background: linear-gradient(135deg, white 0%, {SLATE_50} 100%);
    border: 1px solid {SLATE_100};
    border-radius: 24px;
    padding: 48px 40px;
    margin-bottom: 28px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.03);
}}
.tag-eyebrow {{
    display: inline-block;
    background: {CORAL_50};
    color: {CORAL};
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 6px 12px;
    border-radius: 999px;
    margin-bottom: 18px;
}}
.tag-h1 {{
    font-size: 2.6rem;
    font-weight: 700;
    color: {NAVY};
    line-height: 1.1;
    letter-spacing: -0.02em;
    margin: 0 0 14px 0;
}}
.tag-h1 .accent {{ color: {CORAL}; }}
.tag-sub {{
    font-size: 1.08rem;
    color: {SLATE_500};
    max-width: 720px;
    line-height: 1.55;
    margin: 0;
}}
.tag-kpi-row {{
    display: flex;
    gap: 32px;
    flex-wrap: wrap;
    margin-top: 32px;
    padding-top: 28px;
    border-top: 1px solid {SLATE_100};
}}
.tag-kpi {{
    flex: 1;
    min-width: 140px;
}}
.tag-kpi-label {{
    font-size: 0.72rem;
    color: {SLATE_500};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 6px;
}}
.tag-kpi-value {{
    font-size: 2.2rem;
    font-weight: 700;
    color: {NAVY};
    line-height: 1;
}}
.tag-kpi-value.coral {{ color: {CORAL}; }}
.tag-kpi-value.green {{ color: {GREEN}; }}
.tag-kpi-value.orange {{ color: {ORANGE}; }}
.tag-kpi-hint {{
    font-size: 0.82rem;
    color: {SLATE_500};
    margin-top: 4px;
}}

/* Card generica */
.tag-card {{
    background: white;
    border: 1px solid {SLATE_100};
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 14px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.03);
}}

/* Recommendation card */
.tag-rec-card {{
    background: white;
    border: 1px solid {SLATE_100};
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 8px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.03);
}}
.tag-rec-head {{
    display: flex;
    gap: 14px;
    align-items: flex-start;
    margin-bottom: 12px;
}}
.tag-rec-icon {{
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
    flex-shrink: 0;
}}
.tag-rec-meta {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
    flex-wrap: wrap;
}}
.tag-rec-sev {{
    font-size: 0.7rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.tag-rec-cat {{
    color: {SLATE_500};
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
.tag-rec-title {{
    font-weight: 700;
    font-size: 1.05rem;
    color: {NAVY};
    line-height: 1.35;
}}
.tag-rec-why {{
    color: {SLATE_700};
    font-size: 0.92rem;
    line-height: 1.55;
    padding-top: 4px;
    border-top: 1px solid {SLATE_100};
    margin-top: 4px;
    padding-top: 14px;
}}

/* Quick-nav card cliccabili (sezione "Dove andare" sulla home) */
.tag-nav-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-top: 4px;
}}
@media (max-width: 1100px) {{
    .tag-nav-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}
.tag-nav-card {{
    display: block;
    background: white;
    border: 1px solid {SLATE_100};
    border-radius: 14px;
    padding: 20px 22px;
    text-decoration: none !important;
    color: {NAVY} !important;
    transition: all .14s ease;
    box-shadow: 0 1px 2px rgba(15,23,42,0.03);
    cursor: pointer;
}}
.tag-nav-card:hover {{
    border-color: {CORAL};
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(233,78,27,0.10);
    text-decoration: none !important;
}}
.tag-nav-card-icon {{
    font-size: 1.8rem;
    margin-bottom: 8px;
    line-height: 1;
}}
.tag-nav-card-title {{
    font-weight: 700;
    font-size: 1.02rem;
    color: {NAVY};
    margin-bottom: 4px;
}}
.tag-nav-card-desc {{
    color: {SLATE_500};
    font-size: 0.86rem;
    line-height: 1.45;
}}
.tag-nav-card:hover .tag-nav-card-title {{ color: {CORAL}; }}

/* Response card (per feed risposte) */
.tag-resp-card {{
    background: white;
    border: 1px solid {SLATE_100};
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.03);
    transition: box-shadow .12s ease;
}}
.tag-resp-card:hover {{
    box-shadow: 0 4px 14px rgba(15,23,42,0.06);
}}
.tag-resp-head {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid {SLATE_100};
}}
.tag-resp-model {{
    background: {NAVY};
    color: white;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    text-transform: lowercase;
    letter-spacing: 0.02em;
}}
.tag-resp-prompt {{
    color: {SLATE_700};
    font-weight: 500;
    flex: 1;
    min-width: 200px;
}}
.tag-resp-time {{
    color: {SLATE_500};
    font-size: 0.82rem;
}}
.tag-resp-text {{
    color: {SLATE_700};
    line-height: 1.65;
    font-size: 0.96rem;
    margin: 8px 0 14px 0;
}}
.tag-resp-text p {{ margin: 0 0 10px 0; }}

/* Badge */
.tag-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
.tag-badge.success {{ background: {GREEN_50}; color: {GREEN}; }}
.tag-badge.warn    {{ background: {ORANGE_50}; color: {ORANGE}; }}
.tag-badge.danger  {{ background: #FEF2F2; color: {RED}; }}
.tag-badge.neutral {{ background: {SLATE_100}; color: {SLATE_500}; }}
.tag-badge.coral   {{ background: {CORAL_50}; color: {CORAL}; }}

/* Citation chip */
.tag-cit {{
    display: flex;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid {SLATE_100};
    background: {SLATE_50};
    margin: 6px 0;
    font-size: 0.88rem;
}}
.tag-cit.target {{ border-left: 3px solid {GREEN}; background: {GREEN_50}; }}
.tag-cit.competitor {{ border-left: 3px solid {ORANGE}; background: {ORANGE_50}; }}
.tag-cit-pos {{
    font-weight: 700;
    color: {SLATE_500};
    min-width: 22px;
}}
.tag-cit-body {{ flex: 1; min-width: 0; }}
.tag-cit-domain {{
    font-weight: 600;
    color: {NAVY};
    font-size: 0.82rem;
}}
.tag-cit-title {{
    color: {SLATE_700};
    font-size: 0.86rem;
    margin-top: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}

/* Section header */
.tag-section-eyebrow {{
    color: {CORAL};
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 4px 0;
}}
.tag-section-title {{
    font-size: 1.5rem;
    font-weight: 700;
    color: {NAVY};
    margin: 0 0 6px 0;
    letter-spacing: -0.01em;
}}
.tag-section-sub {{
    color: {SLATE_500};
    margin: 0 0 18px 0;
    font-size: 0.95rem;
}}

/* ============ CHAT-STYLE RESPONSES (HubSpot-like) ============ */
.tag-chat {{
    background: white;
    border: 1px solid {SLATE_100};
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 18px;
    box-shadow: 0 1px 2px rgba(15,23,42,0.03);
}}
.tag-chat-head {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    padding-bottom: 14px;
    margin-bottom: 14px;
    border-bottom: 1px solid {SLATE_100};
}}
.tag-chat-engine {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 600;
    color: {NAVY};
}}
.tag-chat-engine-text {{
    display: flex;
    flex-direction: column;
    line-height: 1.1;
    gap: 2px;
}}
.tag-chat-engine-name {{
    font-weight: 700;
    color: {NAVY};
    font-size: 0.95rem;
}}
.tag-chat-engine-version {{
    color: {SLATE_500};
    font-size: 0.72rem;
    font-weight: 500;
    font-family: ui-monospace, 'SF Mono', Menlo, monospace;
}}
.tag-chat-run-meta {{
    color: {SLATE_500};
    font-size: 0.86rem;
}}

/* Prompt bubble - allineato a destra come l'utente in una chat */
.tag-bubble-row {{
    display: flex;
    justify-content: flex-end;
    margin: 10px 0 16px 0;
}}
.tag-bubble-prompt {{
    background: {CORAL_50};
    color: {NAVY};
    padding: 12px 16px;
    border-radius: 18px 18px 4px 18px;
    max-width: 75%;
    font-size: 0.94rem;
    line-height: 1.5;
    border: 1px solid {CORAL_100};
}}

/* Response bubble - allineato a sinistra con avatar + nome modello */
.tag-bubble-resp-row {{
    display: flex;
    gap: 12px;
    align-items: flex-start;
}}
.tag-bubble-resp-engine {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    width: 56px;
}}
.tag-bubble-resp-engine-name {{
    font-size: 0.7rem;
    color: {SLATE_500};
    font-weight: 600;
    text-align: center;
    line-height: 1.1;
}}

/* Variante compatta per layout multi-colonna (es. ripetizioni affiancate) */
.tag-chat-compact {{
    padding: 14px 16px;
    margin-bottom: 10px;
}}
.tag-chat-compact .tag-bubble-resp {{
    font-size: 0.86rem;
    padding: 10px 14px;
    line-height: 1.55;
}}
.tag-chat-compact .tag-chat-head {{
    padding-bottom: 10px;
    margin-bottom: 10px;
}}
.tag-bubble-resp {{
    background: {SLATE_50};
    border: 1px solid {SLATE_100};
    color: {SLATE_700};
    padding: 14px 18px;
    border-radius: 4px 18px 18px 18px;
    flex: 1;
    line-height: 1.65;
    font-size: 0.95rem;
    word-wrap: break-word;
    font-family: 'Poppins', system-ui, sans-serif;
    overflow-wrap: anywhere;
}}
.tag-bubble-resp p {{ margin: 0 0 10px 0; }}
.tag-bubble-resp p:last-child {{ margin-bottom: 0; }}
.tag-bubble-resp h1, .tag-bubble-resp h2, .tag-bubble-resp h3,
.tag-bubble-resp h4, .tag-bubble-resp h5, .tag-bubble-resp h6 {{
    color: {NAVY};
    margin: 14px 0 6px 0;
    font-weight: 700;
    line-height: 1.3;
}}
.tag-bubble-resp h1 {{ font-size: 1.2rem; }}
.tag-bubble-resp h2 {{ font-size: 1.1rem; }}
.tag-bubble-resp h3 {{ font-size: 1.0rem; }}
.tag-bubble-resp h4, .tag-bubble-resp h5, .tag-bubble-resp h6 {{ font-size: 0.96rem; }}
.tag-bubble-resp strong {{ color: {NAVY}; font-weight: 700; }}
.tag-bubble-resp em {{ font-style: italic; }}
.tag-bubble-resp ul, .tag-bubble-resp ol {{
    margin: 6px 0 12px 0;
    padding-left: 22px;
}}
.tag-bubble-resp li {{ margin: 3px 0; }}
.tag-bubble-resp a {{
    color: {CORAL};
    text-decoration: underline;
    text-decoration-color: {CORAL_100};
    word-break: break-all;
}}
.tag-bubble-resp a:hover {{ text-decoration-color: {CORAL}; }}
.tag-bubble-resp code {{
    background: white;
    border: 1px solid {SLATE_100};
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.88em;
    font-family: ui-monospace, 'SF Mono', Menlo, monospace;
    color: {NAVY};
}}
.tag-bubble-resp pre {{
    background: white;
    border: 1px solid {SLATE_100};
    padding: 12px 14px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 10px 0;
    font-size: 0.86rem;
}}
.tag-bubble-resp pre code {{ background: transparent; border: none; padding: 0; }}
.tag-bubble-resp blockquote {{
    border-left: 3px solid {CORAL};
    padding: 4px 0 4px 12px;
    margin: 10px 0;
    color: {SLATE_700};
    font-style: italic;
}}
.tag-bubble-resp table {{
    border-collapse: collapse;
    margin: 10px 0;
    font-size: 0.88rem;
    width: 100%;
    background: white;
    border-radius: 8px;
    overflow: hidden;
}}
.tag-bubble-resp th, .tag-bubble-resp td {{
    border: 1px solid {SLATE_100};
    padding: 8px 12px;
    text-align: left;
    vertical-align: top;
}}
.tag-bubble-resp th {{ background: {SLATE_50}; font-weight: 700; color: {NAVY}; }}
.tag-bubble-resp hr {{
    border: none;
    border-top: 1px solid {SLATE_100};
    margin: 14px 0;
}}

/* Model avatar circles */
.tag-avatar {{
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
    padding: 7px;
    box-sizing: border-box;
}}
.tag-avatar svg {{
    width: 100%;
    height: 100%;
    display: block;
}}
.tag-avatar.chatgpt    {{ background: #10A37F; }}
.tag-avatar.claude     {{ background: #D97757; }}
.tag-avatar.perplexity {{ background: #20808D; }}
.tag-avatar.gemini     {{ background: linear-gradient(135deg, #4285F4, #9B72CB, #F4B400); }}
.tag-avatar.unknown    {{ background: {SLATE_500}; }}

.tag-avatar-sm {{
    width: 24px;
    height: 24px;
    padding: 4px;
}}

/* Run badge "Brand mentioned in this run" */
.tag-run-status {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
}}
.tag-run-status.mentioned {{
    background: {GREEN_50};
    color: {GREEN};
}}
.tag-run-status.not-mentioned {{
    background: {SLATE_100};
    color: {SLATE_500};
}}
.tag-run-status.gap {{
    background: {ORANGE_50};
    color: {ORANGE};
}}

/* Engine summary cards (top of Risposte / Prompt Detail) */
.tag-engine-card {{
    background: white;
    border: 1px solid {SLATE_100};
    border-radius: 14px;
    padding: 18px 20px;
    display: flex;
    align-items: center;
    gap: 14px;
}}
.tag-engine-card .tag-avatar {{ width: 42px; height: 42px; font-size: 0.82rem; }}
.tag-engine-name {{
    font-weight: 600;
    color: {NAVY};
    font-size: 1rem;
}}
.tag-engine-stat {{
    color: {SLATE_500};
    font-size: 0.88rem;
    margin-top: 2px;
}}

/* ============ SIDEBAR RESTYLE ============ */
/* Nasconde il nav nativo Streamlit: ricostruiamo noi un menu custom
   pulito col brand SOPRA. Lasciamo lo header trasparente. */
[data-testid="stSidebarNav"] {{
    display: none !important;
}}
[data-testid="stSidebarHeader"] {{
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    padding-top: 1rem;
}}

/* Nav sidebar custom (link HTML diretti) */
.tag-sidebar-nav {{
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: 18px;
    padding: 0 4px;
}}
.tag-sidebar-nav-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    border-radius: 8px;
    color: {SLATE_700} !important;
    font-weight: 500;
    font-size: 0.92rem;
    text-decoration: none !important;
    transition: background .12s ease, color .12s ease;
}}
.tag-sidebar-nav-item:hover {{
    background: {CORAL_50};
    color: {CORAL} !important;
    text-decoration: none !important;
}}
.tag-sidebar-nav-icon {{
    font-size: 1.05rem;
    width: 22px;
    display: inline-flex;
    justify-content: center;
}}
.tag-sidebar-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 8px 16px 8px;
    border-bottom: 1px solid {SLATE_100};
    margin-bottom: 18px;
}}
.tag-sidebar-logo {{
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: {CORAL};
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.92rem;
    letter-spacing: -0.02em;
}}
.tag-sidebar-title {{
    font-weight: 700;
    font-size: 1rem;
    color: {NAVY};
    line-height: 1.1;
}}
.tag-sidebar-tagline {{
    font-size: 0.72rem;
    color: {SLATE_500};
    margin-top: 2px;
}}
.tag-sidebar-beta {{
    display: inline-block;
    background: {CORAL_50};
    color: {CORAL};
    font-size: 0.6rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 6px;
    vertical-align: middle;
    letter-spacing: 0.04em;
}}
.tag-sidebar-section {{
    color: {SLATE_500};
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 16px 8px 8px 8px;
}}
.tag-sidebar-brand-pill {{
    background: white;
    border: 1px solid {SLATE_100};
    border-radius: 10px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 0 4px 12px 4px;
    cursor: default;
}}
.tag-sidebar-brand-pill-name {{
    font-weight: 600;
    color: {NAVY};
    font-size: 0.88rem;
}}
.tag-sidebar-brand-pill-domain {{
    color: {SLATE_500};
    font-size: 0.74rem;
    margin-top: 1px;
}}

/* Page title cleaner */
.tag-page-head {{
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 24px;
}}
.tag-page-icon {{
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: {CORAL_50};
    color: {CORAL};
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
    flex-shrink: 0;
}}
.tag-page-title {{
    font-size: 1.8rem;
    font-weight: 700;
    color: {NAVY};
    margin: 0;
    letter-spacing: -0.01em;
}}
.tag-page-sub {{
    color: {SLATE_500};
    margin: 4px 0 0 0;
}}
</style>
"""


def apply_style() -> None:
    """Inietta CSS globale. Da chiamare subito dopo st.set_page_config()."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(icon: str, title: str, sub: str | None = None) -> None:
    """Header pagina coerente con palette TAG (sostituisce st.title)."""
    sub_html = f'<p class="tag-page-sub">{sub}</p>' if sub else ""
    st.markdown(
        f"""
        <div class="tag-page-head">
            <div class="tag-page-icon">{icon}</div>
            <div>
                <h1 class="tag-page-title">{title}</h1>
                {sub_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(eyebrow: str, title: str, sub: str | None = None) -> None:
    """Header sezione stile HubSpot (eyebrow coral + titolo + sub)."""
    sub_html = f'<p class="tag-section-sub">{sub}</p>' if sub else ""
    st.markdown(
        f"""
        <div style="margin-top:8px">
            <p class="tag-section-eyebrow">{eyebrow}</p>
            <h2 class="tag-section-title">{title}</h2>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "neutral") -> str:
    """Restituisce HTML di un badge inline (success/warn/danger/coral/neutral)."""
    return f'<span class="tag-badge {kind}">{text}</span>'


# ---------- Model avatar / engine display ----------

_ENGINE_META = {
    # match per substring sul model_id
    "chatgpt": ("ChatGPT", "chatgpt"),
    "gpt-":    ("ChatGPT", "chatgpt"),
    "openai":  ("ChatGPT", "chatgpt"),
    "claude":  ("Claude", "claude"),
    "anthropic": ("Claude", "claude"),
    "sonnet":  ("Claude", "claude"),
    "opus":    ("Claude", "claude"),
    "haiku":   ("Claude", "claude"),
    "perplex": ("Perplexity", "perplexity"),
    "sonar":   ("Perplexity", "perplexity"),
    "gemini":  ("Gemini", "gemini"),
    "google":  ("Gemini", "gemini"),
}

# Loghi SVG inline semplificati (riconoscibili ma non i marchi originali).
# Tutti su viewBox 24x24, fill="white" così riempiono il cerchio colorato.
_ENGINE_SVG = {
    # OpenAI: rotonda "knot" stilizzata
    "chatgpt": '<svg viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .744 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.738l2.02 1.168.014.014v5.585a4.504 4.504 0 0 1-4.47 4.531zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332l-5.864 3.39a4.5 4.5 0 0 1-5.149-2.183zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.974V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2l4.825 2.787a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.418-.667zm2.011-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897l5.831-3.366a4.5 4.5 0 0 1 6.708 4.66zm-12.64 4.135l-2.02-1.164V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/></svg>',
    # Anthropic Claude: asterisco / stella stilizzata
    "claude": '<svg viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M6.5 4.5h3.4l4.3 11.1h-3.2l-.9-2.5H5.6l-.9 2.5H1.6L6.5 4.5zm.4 6.3h2.6L8.2 7.3 6.9 10.8zM13.6 4.5h3.3L21.4 17h-3.3L13.6 4.5z"/></svg>',
    # Perplexity: cerchio con "P" stilizzata
    "perplexity": '<svg viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M11.07 0v3.394L4.797 8.668v6.94L1.99 18V8.668zM12.93 0L23 8.575v9.426l-2.808-2.392V8.668L12.93 3.394zm0 5.86l6.04 5.144L12.93 16.1zM11.07 7.9v8.16l-6.067-5.137zM11.07 19.7V24H4.797v-4.3zM12.93 19.7h6.273V24H12.93z"/></svg>',
    # Gemini: stella sparkle a 4 punte
    "gemini": '<svg viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L13.5 9.5L21 11L13.5 12.5L12 20L10.5 12.5L3 11L10.5 9.5L12 2Z"/></svg>',
    # Fallback unknown: cerchio con punto interrogativo
    "unknown": '<svg viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg"><text x="12" y="17" text-anchor="middle" font-size="14" font-weight="700" font-family="Poppins, sans-serif">?</text></svg>',
}


def model_meta(model_id: str) -> tuple[str, str]:
    """Restituisce (display_name, css_class) per un model_id."""
    if not model_id:
        return ("Unknown", "unknown")
    mid = model_id.lower()
    for key, meta in _ENGINE_META.items():
        if key in mid:
            return meta
    return (model_id, "unknown")


def model_avatar(model_id: str, size: str = "") -> str:
    """HTML del cerchio-avatar del modello con LOGO SVG inline. size: '' o 'sm'."""
    _name, cls = model_meta(model_id)
    svg = _ENGINE_SVG.get(cls, _ENGINE_SVG["unknown"])
    size_cls = f" tag-avatar-{size}" if size else ""
    return f'<div class="tag-avatar {cls}{size_cls}">{svg}</div>'


def render_chat_response(
    *,
    model_id: str,
    prompt_text: str,
    response_text_html: str,
    created_at_str: str,
    has_target_mention: bool,
    has_target_citation: bool,
    run_label: str | None = None,
    extra_badges_html: str = "",
    show_prompt: bool = True,
    compact: bool = False,
) -> str:
    """Restituisce l'HTML di una risposta in chat-style (HubSpot-like).

    Args:
        show_prompt: se False, omette la bubble del prompt (utile quando il prompt
            è già mostrato nel page header / o stiamo affiancando più risposte allo
            stesso prompt).
        compact: se True, riduce padding e font per layout multi-colonna.

    Il response_text_html dev'essere già HTML-safe (es. da highlight_brands_html).
    """
    display_name, _ = model_meta(model_id)
    if has_target_citation:
        status_html = (
            '<span class="tag-run-status mentioned">'
            '✓ Brand citato in questa risposta</span>'
        )
    elif has_target_mention:
        status_html = (
            '<span class="tag-run-status gap">'
            '⚠ Menzionato senza citazione</span>'
        )
    else:
        status_html = (
            '<span class="tag-run-status not-mentioned">'
            'Brand non menzionato</span>'
        )

    run_html = (
        f'<span class="tag-chat-run-meta">{run_label}</span>' if run_label else ""
    )

    import html as _html
    safe_prompt = _html.escape(prompt_text)
    avatar = model_avatar(model_id)
    chat_cls = "tag-chat tag-chat-compact" if compact else "tag-chat"

    # Header (modello + versione + status). Sempre visibile, anche in compact.
    head_html = (
        f'<div class="tag-chat-head">'
        f'<div class="tag-chat-engine">{model_avatar(model_id, "sm")}'
        f'<div class="tag-chat-engine-text">'
        f'<span class="tag-chat-engine-name">{display_name}</span>'
        f'<span class="tag-chat-engine-version">{model_id}</span>'
        f'</div></div>'
        f'{run_html}<div style="flex:1"></div>{status_html}{extra_badges_html}'
        f'</div>'
    )

    # Prompt bubble (opzionale)
    prompt_html = (
        f'<div class="tag-bubble-row"><div class="tag-bubble-prompt">{safe_prompt}</div></div>'
        if show_prompt else ""
    )

    # Response row: avatar + NOME del modello + bubble
    resp_html = (
        f'<div class="tag-bubble-resp-row">'
        f'<div class="tag-bubble-resp-engine">'
        f'{avatar}'
        f'<div class="tag-bubble-resp-engine-name">{display_name}</div>'
        f'</div>'
        f'<div class="tag-bubble-resp">{response_text_html}</div>'
        f'</div>'
    )

    return (
        f'<div class="{chat_cls}">'
        f'{head_html}'
        f'{prompt_html}'
        f'{resp_html}'
        f'<div style="color:{SLATE_500};font-size:0.78rem;margin-top:10px;text-align:right">{created_at_str}</div>'
        f'</div>'
    )


def engine_summary_card(model_id: str, label: str, stat: str) -> str:
    """HTML di una card riassuntiva per engine (es. 'Mentioned 5 out of 10 times')."""
    display_name, _ = model_meta(model_id)
    return (
        f'<div class="tag-engine-card">{model_avatar(model_id)}'
        f'<div><div class="tag-engine-name">{display_name}</div>'
        f'<div class="tag-engine-stat">{stat}</div></div></div>'
    )


def render_sidebar(
    *,
    brand_name: str = "Talent Garden",
    brand_domain: str = "talentgarden.com",
    current_kpi_label: str | None = None,
    current_kpi_value: str | None = None,
    cost_usd: float | None = None,
    n_runs: int | None = None,
) -> None:
    """Sidebar restyled: brand block PRIMA del menu pagine (nav nativo nascosto via CSS,
    sostituito con st.page_link custom). Sotto: brand selector + KPI + engine + footer.
    """
    # ---------- BRAND BLOCK (in cima, sopra il menu) ----------
    st.sidebar.markdown(
        """
        <div class="tag-sidebar-brand">
            <div class="tag-sidebar-logo">LV</div>
            <div>
                <div class="tag-sidebar-title">LLM Visibility<span class="tag-sidebar-beta">BETA</span></div>
                <div class="tag-sidebar-tagline">by Talent Garden</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------- NAV CLIENT-SIDE (st.page_link) ----------
    # st.page_link naviga SENZA reload completo della pagina: la sessione resta
    # attiva, niente re-import né re-render da zero → cambio pagina molto più
    # veloce dei vecchi link <a target="_self"> (che facevano un full reload).
    nav_pages = [
        ("app.py",                        "Home",            "🏠"),
        ("pages/1_Overview.py",           "Overview",        "📊"),
        ("pages/2_Risposte.py",           "Risposte",        "💬"),
        ("pages/3_Prompts.py",            "Prompts",         "📝"),
        ("pages/4_Prompt_Detail.py",      "Prompt Detail",   "🔬"),
        ("pages/5_Citations.py",          "Citations",       "🔗"),
        ("pages/6_Models.py",             "Models",          "🤖"),
        ("pages/8_Recommendations.py",    "Recommendations", "🎯"),
        ("pages/7_Costi_e_Run.py",        "Costi & Run",     "💰"),
    ]
    for path, label, icon in nav_pages:
        try:
            st.sidebar.page_link(path, label=label, icon=icon, use_container_width=True)
        except Exception:  # noqa: BLE001
            # fallback robusto se il path non è risolvibile in qualche ambiente
            st.sidebar.markdown(
                f'<a href="/{path.split("/")[-1].split("_", 1)[-1].replace(".py", "")}" '
                f'target="_self" class="tag-sidebar-nav-item">{icon} {label}</a>',
                unsafe_allow_html=True,
            )

    # ---------- BRAND MONITORATO ----------
    st.sidebar.markdown(
        '<div class="tag-sidebar-section">Brand monitorato</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"""
        <div class="tag-sidebar-brand-pill">
            <div>
                <div class="tag-sidebar-brand-pill-name">{brand_name}</div>
                <div class="tag-sidebar-brand-pill-domain">{brand_domain}</div>
            </div>
            <div style="color:{SLATE_500};font-size:0.78rem">●</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if current_kpi_value:
        st.sidebar.markdown(
            '<div class="tag-sidebar-section">Citation rate</div>',
            unsafe_allow_html=True,
        )
        st.sidebar.markdown(
            f"""
            <div style="padding:0 4px 12px 4px">
                <div style="font-size:1.7rem;font-weight:700;color:{CORAL};line-height:1">
                    {current_kpi_value}
                </div>
                <div style="color:{SLATE_500};font-size:0.78rem;margin-top:2px">
                    {current_kpi_label or ""}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Cost & Run mini-KPI (sempre visibili nella sidebar)
    if cost_usd is not None or n_runs is not None:
        st.sidebar.markdown(
            '<div class="tag-sidebar-section">Cost & Run</div>',
            unsafe_allow_html=True,
        )
        cost_str = (
            f"${cost_usd:.2f}" if (cost_usd is not None and cost_usd >= 0.01)
            else (f"${(cost_usd or 0)*100:.1f}¢" if cost_usd else "$0.00")
        )
        st.sidebar.markdown(
            f"""
            <div style="display:flex;gap:8px;padding:0 4px 12px 4px">
                <div style="flex:1;background:white;border:1px solid {SLATE_100};
                            border-radius:10px;padding:10px">
                    <div style="color:{SLATE_500};font-size:0.66rem;text-transform:uppercase;
                                letter-spacing:0.05em;font-weight:600">💰 Spesa</div>
                    <div style="font-size:1.1rem;font-weight:700;color:{NAVY};line-height:1.1;
                                margin-top:2px">{cost_str}</div>
                </div>
                <div style="flex:1;background:white;border:1px solid {SLATE_100};
                            border-radius:10px;padding:10px">
                    <div style="color:{SLATE_500};font-size:0.66rem;text-transform:uppercase;
                                letter-spacing:0.05em;font-weight:600">🏃 Run</div>
                    <div style="font-size:1.1rem;font-weight:700;color:{NAVY};line-height:1.1;
                                margin-top:2px">{n_runs if n_runs is not None else "—"}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.sidebar.markdown(
        '<div class="tag-sidebar-section">Engine monitorati</div>',
        unsafe_allow_html=True,
    )
    engines_html = (
        '<div style="display:flex;gap:6px;flex-wrap:wrap;padding:0 4px 12px 4px">'
    )
    for mid in ("chatgpt", "claude", "perplexity", "gemini"):
        engines_html += model_avatar(mid, "sm")
    engines_html += "</div>"
    st.sidebar.markdown(engines_html, unsafe_allow_html=True)

    st.sidebar.markdown(
        '<div class="tag-sidebar-section">Aggiornamento</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(
        "Batch settimanale automatico via GitHub Actions.\n\n"
        "Manuale: `python -m scripts.run_batch --repeat 1`"
    )
