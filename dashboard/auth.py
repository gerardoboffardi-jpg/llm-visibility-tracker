"""Gate password per Streamlit Cloud (singola password condivisa).

Se `APP_PASSWORD` non è settata in secrets o env, l'auth è disattivata
(comodo per uso locale).

L'autenticazione viene persistita in un cookie del browser (hash della
password, non la password in chiaro) così da NON richiedere il login ad ogni
reload della pagina. `st.session_state` da solo non basta: Streamlit lo azzera
ad ogni ricaricamento completo della pagina.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import os

import streamlit as st

try:
    import extra_streamlit_components as stx  # type: ignore
    _HAS_COOKIES = True
except Exception:  # noqa: BLE001
    _HAS_COOKIES = False

_COOKIE_NAME = "llmvt_auth"
_COOKIE_DAYS = 30


def _expected_password() -> str | None:
    # Priorità: env > st.secrets
    pwd = os.getenv("APP_PASSWORD")
    if pwd:
        return pwd
    try:
        return st.secrets.get("APP_PASSWORD")
    except Exception:
        return None


def _expected_token(expected: str) -> str:
    """Token derivato dalla password: cambiando APP_PASSWORD i cookie vecchi
    diventano automaticamente invalidi."""
    return hashlib.sha256(f"llmvt::{expected}".encode()).hexdigest()


def _cookie_manager() -> "stx.CookieManager":
    # NON usare @st.cache_resource: CookieManager è un widget (component) e
    # Streamlit vieta i widget dentro funzioni cached. Va istanziato a ogni run;
    # il `key` fisso garantisce che sia lo stesso component fra le pagine.
    return stx.CookieManager(key="llmvt_cookie_mgr")


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

    token = _expected_token(expected)

    # Già autenticato in questa sessione
    if st.session_state.get("_authenticated"):
        return True

    # Ripristina l'auth dal cookie LEGGENDOLO in modo sincrono via st.context.
    # Nativo Streamlit (>=1.37), nessun componente → nessun doppio caricamento.
    try:
        if st.context.cookies.get(_COOKIE_NAME) == token:
            st.session_state["_authenticated"] = True
            return True
    except Exception:  # noqa: BLE001
        pass

    # --- Non autenticato: schermata di login. ---
    # Il componente cookie viene istanziato SOLO qui (serve per SCRIVERE il
    # cookie al login), così le pagine autenticate non lo toccano mai.
    cookies = _cookie_manager() if _HAS_COOKIES else None

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
                    # Salva il cookie così il login sopravvive ai reload
                    if cookies is not None:
                        try:
                            cookies.set(
                                _COOKIE_NAME,
                                token,
                                expires_at=_dt.datetime.now() + _dt.timedelta(days=_COOKIE_DAYS),
                            )
                        except Exception:  # noqa: BLE001
                            pass
                    st.rerun()
                else:
                    st.error("Password errata")
    return False
