"""Streamlit session state for the dummy login (Task 11.2, rules.md §24).

Thin helpers over a mutable mapping so the logic is unit-testable without
a Streamlit runtime: pass ``st.session_state`` in the app and a plain
``dict`` in tests. Only one key is ever used; the stored value is the
plain-dict form of :class:`User`.
"""

from __future__ import annotations

from typing import Any, MutableMapping

from acadexa.dashboard.auth import User

SESSION_USER_KEY: str = "acadexa_current_user"


def login(state: MutableMapping[str, Any], user: User) -> None:
    """Establish a demo session for ``user``."""
    state[SESSION_USER_KEY] = user.to_dict()


def logout(state: MutableMapping[str, Any]) -> None:
    """Clear the demo session."""
    state.pop(SESSION_USER_KEY, None)


def get_current_user(state: MutableMapping[str, Any]) -> User | None:
    """Return the session user, or None when logged out."""
    raw = state.get(SESSION_USER_KEY)
    if raw is None:
        return None
    if isinstance(raw, User):
        return raw
    return User.from_dict(raw)


def is_authenticated(state: MutableMapping[str, Any]) -> bool:
    """Return True when a demo session is active."""
    return get_current_user(state) is not None
