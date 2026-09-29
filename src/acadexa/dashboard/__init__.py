"""Acadexa Streamlit dashboard package (Phase 11, folder_structure.md §14).

Presentation layer only: dummy login, session state, centralized
role/scope resolution and bounded MongoDB serving reads. Heavy analytics
stay in PySpark; Streamlit consumes prepared gold/serving data.
"""

from acadexa.dashboard import auth, config, data_access, permissions, session

__all__ = ["auth", "config", "data_access", "permissions", "session"]
