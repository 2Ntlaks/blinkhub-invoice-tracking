"""Health check, the demo user list and "who am I"."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import any_user, get_session
from app.models import User
from app.schemas import HealthOut, UserOut
from app.services import user_out

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/users", response_model=list[UserOut])
def list_users(session: Session = Depends(get_session)) -> list[UserOut]:
    """Open to everyone: the demo role switcher needs it before anyone has picked a user."""
    users = session.scalars(select(User).options(selectinload(User.supplier)).order_by(User.id))
    return [user_out(u) for u in users]


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(any_user)) -> UserOut:
    return user_out(user)
