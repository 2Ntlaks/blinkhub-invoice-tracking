"""Demo identity: the ``X-User-Id`` header says which seeded user is acting (contract section 1).

Real sign-in is out of scope for the prototype. Permission checks are still real:
every endpoint declares which roles may call it, and suppliers only ever see their
own records.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import datetime

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import is_valid_id
from app.enums import ErrorCode, Role
from app.errors import AppError
from app.models import User

#: Strict ASCII integer check: rejects "--1", "+1", decimals, and non-ASCII digits.
_INT_PATTERN = re.compile(r"-?\d+", re.ASCII)


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_now(request: Request) -> datetime:
    """The current time for this request. Tests replace the clock to freeze time."""
    return request.app.state.clock()


def current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    session: Session = Depends(get_session),
) -> User:
    raw = (x_user_id or "").strip()
    if not _INT_PATTERN.fullmatch(raw):
        raise AppError(ErrorCode.UNAUTHENTICATED, "Send the X-User-Id header with a valid user id.")
    user_id = int(raw)
    if not is_valid_id(user_id):
        raise AppError(ErrorCode.UNAUTHENTICATED, f"Unknown user id {raw}.")
    user = session.scalars(
        select(User).options(selectinload(User.supplier)).where(User.id == user_id)
    ).first()
    if user is None:
        raise AppError(ErrorCode.UNAUTHENTICATED, f"Unknown user id {raw}.")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Dependency factory: let the request through only for the given roles."""

    def guard(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            allowed = ", ".join(roles)
            raise AppError(ErrorCode.FORBIDDEN, f"This action is for {allowed} users only.")
        return user

    return guard


any_user = current_user
finance_only = require_roles(Role.FINANCE)
internal_staff = require_roles(Role.FINANCE, Role.MANAGER)
supplier_only = require_roles(Role.SUPPLIER)
