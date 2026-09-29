"""Dummy login for the Streamlit dashboard (Task 11.2, rules.md §24).

Demonstration authentication only: a configured dummy user is resolved to a
role and analytical scope. This is not production security — no passwords
exist, no real credentials are stored, and no external identity provider is
involved. Streamlit-free so the logic is unit-testable without a UI runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from acadexa.config.loader import load_config_file
from acadexa.dashboard.config import DEFAULT_DUMMY_USERS_PATH

# The four approved dashboard roles (docs/memory.md §3, features.md F-A02).
ROLE_UNIVERSITY_ADMIN: str = "University Admin"
ROLE_SCHOOL_ADMIN: str = "School / Department Admin"
ROLE_FACULTY: str = "Faculty"
ROLE_ANALYST: str = "Academic Analyst"

APPROVED_ROLES: tuple[str, ...] = (
    ROLE_UNIVERSITY_ADMIN,
    ROLE_SCHOOL_ADMIN,
    ROLE_FACULTY,
    ROLE_ANALYST,
)


class AuthConfigError(ValueError):
    """Raised when the dummy-user configuration is invalid."""


def _check(condition: bool, message: str) -> None:
    """Raise AuthConfigError with ``message`` when ``condition`` is false."""
    if not condition:
        raise AuthConfigError(message)


@dataclass(frozen=True)
class User:
    """An authenticated dummy user with role and analytical scope."""

    username: str
    display_name: str
    role: str
    school: str | None = None
    department: str | None = None
    courses: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a session-safe plain dictionary."""
        return {
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "school": self.school,
            "department": self.department,
            "courses": list(self.courses),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> User:
        """Reconstruct a User from :meth:`to_dict` output."""
        return cls(
            username=str(data["username"]),
            display_name=str(data.get("display_name", data["username"])),
            role=str(data["role"]),
            school=data.get("school"),
            department=data.get("department"),
            courses=tuple(data.get("courses", []) or []),
        )


def _parse_user(entry: Mapping[str, Any]) -> User:
    """Validate one dummy-user entry and build a :class:`User`."""
    _check(isinstance(entry, Mapping), "Dummy-user entry must be a mapping")
    username = entry.get("username")
    _check(
        isinstance(username, str) and username.strip(),
        "Dummy-user entry missing non-empty 'username'",
    )
    role = entry.get("role")
    _check(
        role in APPROVED_ROLES,
        f"Dummy user {username!r} has unapproved role {role!r}; "
        f"expected one of {list(APPROVED_ROLES)}",
    )
    courses = entry.get("courses", [])
    _check(
        isinstance(courses, list) and all(isinstance(c, str) for c in courses),
        f"Dummy user {username!r}: 'courses' must be a list of strings",
    )
    return User(
        username=username,
        display_name=str(entry.get("display_name", username)),
        role=str(role),
        school=entry.get("school"),
        department=entry.get("department"),
        courses=tuple(courses),
    )


def load_dummy_users(path: Path | str | None = None) -> dict[str, User]:
    """Load configured dummy users keyed by username.

    Args:
        path: Dummy-user TOML file. Defaults to
            ``config/dashboard/dummy_users.toml``.

    Raises:
        AuthConfigError: on missing/duplicate users or unapproved roles.
    """
    target = Path(path) if path is not None else DEFAULT_DUMMY_USERS_PATH
    data = load_config_file(target)
    entries = data.get("users", [])
    _check(isinstance(entries, list) and entries, "No dummy users configured")
    users: dict[str, User] = {}
    for entry in entries:
        user = _parse_user(entry)
        _check(
            user.username not in users,
            f"Duplicate dummy username: {user.username!r}",
        )
        users[user.username] = user
    return users


def authenticate(
    username: str | None, users: Mapping[str, User]
) -> User | None:
    """Resolve a demo login to a :class:`User`, or None for unknown users.

    The dummy login intentionally has no password step; unknown usernames
    simply fail to authenticate.
    """
    if not username:
        return None
    return users.get(username)
