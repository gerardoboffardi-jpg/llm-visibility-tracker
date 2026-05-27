"""Gate password per Streamlit Cloud (singola password condivisa).

Se `APP_PASSWORD` non è settata in secrets o env, l'auth è disattivata
(comodo per uso locale).

Persistenza login:
- Su **Streamlit Cloud** `st.context.cookies` è VUOTO (l'app gira in iframe su
  *.streamlit.app) → la lettura sincrona non funziona. Bisogna leggere il cookie
  con un COMPONENTE JS lato client.
- Usiamo `streamlit-cookies-manager` (EncryptedCookieManager): legge e scrive il
  cookie via componente, con `.ready()` per gestire il caricamento asincrono e
  `.save()` per scrivere. Funziona sia su Cloud sia in locale.

`st.session_state` da solo non basta: Streamlit lo azzera a ogni reload e la
navigazione del sidebar fa reload completi.
"""
from __future__ import annotations

import hashlib
import hmac
import os

import streamlit as st

# La libreria usa il deprecato st.cache (solo per derivare la chiave di
# cifratura): lo rimpiazziamo PRIMA dell'import per evitare il warning in UI.
if hasattr(st, "cache") and hasattr(st, "cache_data"):
    st.cache = st.cache_data  # type: ignore[attr-defined]

try:
    from streamlit_cookies_manager import EncryptedCookieManager  # type: ignore
    _HAS_COOKIES = True
except Exception:  # noqa: BLE001
    _HAS_COOKIES = False

_COOKIE_PREFIX = "llmvt/"
_COOKIE_NAME = "auth"


def _expected_password() -> str | None:
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

    if st.session_state.get("_authenticated"):
        return True

    cookies = None
    if _HAS_COOKIES:
        cookies = EncryptedCookieManager(prefix=_COOKIE_PREFIX, password=expected)
        # Attende il caricamento del cookie dal browser (componente JS): è il
        # passaggio che funziona anche su Streamlit Cloud, dove st.context è vuoto.
        if not cookies.ready():
            st.stop()
        if cookies.get(_COOKIE_NAME) == token:
            st.session_state["_authenticated"] = True
            return True

    # --- Non autenticato: schermata di login. ---
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
                    if cookies is not None:
                        try:
                            cookies[_COOKIE_NAME] = token
                            cookies.save()  # scrive il cookie nel browser
                        except Exception:  # noqa: BLE001
                            pass
                    st.rerun()
                else:
                    st.error("Password errata")
    return False
