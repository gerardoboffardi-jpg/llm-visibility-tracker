"""Gate password per Streamlit Cloud (singola password condivisa).

Se `APP_PASSWORD` non è settata in secrets o env, l'auth è disattivata
(comodo per uso locale).

Persistenza login — approccio ibrido (diagnosticato sul campo):
- **LETTURA**: `st.context.cookies` (nativo Streamlit, SINCRONO). Legge i cookie
  reali del browser senza componenti → nessun flash, nessuna race asincrona,
  funziona a ogni reload completo (anche con la navigazione del sidebar che usa
  link <a>).
- **SCRITTURA**: `streamlit-cookies-controller` (solo al login). Il suo `set()`
  scrive un cookie di prima parte che persiste; verificato che `st.context`
  lo rilegge correttamente al reload successivo.

`st.session_state` da solo non basta: Streamlit lo azzera a ogni reload, e la
navigazione del sidebar fa reload completi.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import streamlit as st

try:
    from streamlit_cookies_controller import CookieController  # type: ignore
    _HAS_COOKIES = True
except Exception:  # noqa: BLE001
    _HAS_COOKIES = False

_COOKIE_NAME = "llmvt_auth"
_COOKIE_MAX_AGE_DAYS = 30


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


def _read_cookie_token() -> str | None:
    """Legge il token dal cookie in modo sincrono (nativo, niente componente)."""
    try:
        return st.context.cookies.get(_COOKIE_NAME)
    except Exception:  # noqa: BLE001
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

    token = _expected_token(expected)

    # Già autenticato in questa sessione
    if st.session_state.get("_authenticated"):
        return True

    # Ripristino dal cookie (lettura sincrona via st.context): funziona a ogni
    # reload completo, niente flash.
    if _read_cookie_token() == token:
        st.session_state["_authenticated"] = True
        return True

    # --- DEBUG temporaneo: diagnostica stato cookie (rimuovere dopo) ---
    with st.expander("🔧 debug cookie (temporaneo)", expanded=True):
        _dbg = {"_HAS_COOKIES": _HAS_COOKIES, "token_atteso": token[:12] + "…"}
        try:
            _ctx = dict(st.context.cookies)
            _dbg["st.context ha llmvt_auth"] = _COOKIE_NAME in _ctx
            _dbg["valore == token"] = _ctx.get(_COOKIE_NAME) == token
            _dbg["chiavi cookie"] = list(_ctx.keys())
        except Exception as e:  # noqa: BLE001
            _dbg["ctx_err"] = str(e)
        try:
            _dbg["host"] = st.context.headers.get("Host")
            _dbg["proto"] = st.context.headers.get("X-Forwarded-Proto")
        except Exception:  # noqa: BLE001
            pass
        st.json(_dbg)

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
                    # Scrive il cookie col componente (solo qui, al login).
                    # secure=True + same_site='lax' servono in contesto HTTPS
                    # (Streamlit Cloud). localhost è considerato secure context
                    # dai browser moderni, quindi funziona anche lì.
                    if _HAS_COOKIES:
                        try:
                            CookieController().set(
                                _COOKIE_NAME,
                                token,
                                max_age=_COOKIE_MAX_AGE_DAYS * 24 * 3600,
                                secure=True,
                                same_site="lax",
                            )
                            time.sleep(0.4)  # tempo al componente per scrivere
                        except Exception:  # noqa: BLE001
                            pass
                    st.rerun()
                else:
                    st.error("Password errata")
    return False
