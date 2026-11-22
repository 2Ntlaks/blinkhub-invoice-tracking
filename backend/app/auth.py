"""Demo identity: the ``X-User-Id`` header says which seeded user is acting (contract section 1).

Real sign-in is out of scope for the prototype. Permission checks are still real:
every endpoint declares which roles may call it, and suppliers only ever see their
own records.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.enums import ErrorCode, Role
from app.errors import AppError
from app.models import User


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
    if x_user_id is None or not x_user_id.strip().lstrip("-").isdigit():
        raise AppError(ErrorCode.UNAUTHENTICATED, "Send the X-User-Id header with a valid user id.")
    user = session.get(User, int(x_user_id))
    if user is None:
        raise AppError(ErrorCode.UNAUTHENTICATED, f"Unknown user id {x_user_id.strip()}.")
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
