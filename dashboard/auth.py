"""Gate password per Streamlit Cloud (singola password condivisa).

Se `APP_PASSWORD` non è settata in secrets o env, l'auth è disattivata
(comodo per uso locale).
"""
from __future__ import annotations

import hmac
import os

import streamlit as st


def _expected_password() -> str | None:
    # Priorità: env > st.secrets
    pwd = os.getenv("APP_PASSWORD")
    if pwd:
        return pwd
    try:
        return st.secrets.get("APP_PASSWORD")
    except Exception:
        return None


def require_password() -> bool:
    """Mostra form password come gate. Ritorna True se autenticato.

    Da chiamare all'inizio di OGNI pagina:
        from dashboard.auth import require_password
        if not require_password():
            st.stop()
    """
    expected = _expected_password()
    if not expected:
        return True  # disattivata

    if st.session_state.get("_authenticated"):
        return True

    st.markdown(
        """
        <div style="max-width:420px;margin:80px auto 24px auto;text-align:center">
            <h1 style="font-size:2rem;margin-bottom:0.3rem">🔍 LLM Visibility Tracker</h1>
            <p style="color:#64748b">Monitora la visibilità di <strong>Talent Garden</strong> negli LLM</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("auth", clear_on_submit=False):
        col_l, col_c, col_r = st.columns([1, 2, 1])
        with col_c:
            pwd = st.text_input("Password", type="password", placeholder="Inserisci la password")
            ok = st.form_submit_button("Entra", type="primary", use_container_width=True)
            if ok:
                if hmac.compare_digest(pwd, expected):
                    st.session_state["_authenticated"] = True
                    st.rerun()
                else:
                    st.error("Password errata")
    return False
