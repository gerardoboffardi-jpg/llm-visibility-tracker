"""Gate password — DISATTIVATO.

Il login è stato rimosso volutamente: il link è condiviso solo con poche persone
fidate, e la persistenza via cookie non funziona in modo affidabile su Streamlit
Cloud (l'app gira in un iframe su *.streamlit.app → i cookie scritti dai
componenti vengono bloccati come terze parti, e `st.context.cookies` è vuoto).

`require_password()` ritorna sempre True, quindi nessuna pagina chiede il login.

Per ri-abilitare in futuro un'autenticazione robusta su Cloud, la via corretta è
`st.login` (OIDC, es. Google) che usa il cookie di sessione nativo di Streamlit
lato server — non un componente. Vedi: https://docs.streamlit.io/develop/api-reference/user/st.login
"""
from __future__ import annotations


def require_password() -> bool:
    """No-op: autenticazione disattivata. Ritorna sempre True."""
    return True
