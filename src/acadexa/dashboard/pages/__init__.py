"""Dashboard analytical pages (Phase 12, folder_structure.md §14).

One module per analytical view; each page reads actual gold/serving data
through :mod:`acadexa.dashboard.data_access` and renders with the shared
layout and components. No page duplicates permission logic (rules.md §25)
or fabricates values (rules.md §23).
"""

from __future__ import annotations
