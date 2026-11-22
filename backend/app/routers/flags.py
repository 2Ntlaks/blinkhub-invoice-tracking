"""Review flags: list (staff) and resolve (finance). Suppliers can never reach these."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import services
from app.auth import finance_only, get_now, get_session, internal_staff
from app.enums import FlagStatus
from app.models import User
from app.schemas import FlagOut, ResolveFlagRequest

router = APIRouter(prefix="/flags", tags=["flags"])


@router.get("", response_model=list[FlagOut])
def list_flags(
    status: FlagStatus | None = Query(default=None),
    _: User = Depends(internal_staff),
    session: Session = Depends(get_session),
) -> list[FlagOut]:
    return services.list_flags(session, status)


@router.post("/{flag_id}/resolve", response_model=FlagOut)
def resolve_flag(
    flag_id: int,
    body: ResolveFlagRequest,
    user: User = Depends(finance_only),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> FlagOut:
    return services.resolve_flag(session, user, flag_id, FlagStatus(body.outcome), body.note, now)
