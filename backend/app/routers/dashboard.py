"""Management dashboard (finance and managers)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app import services
from app.auth import get_now, get_session, internal_staff
from app.models import User
from app.schemas import DashboardOut

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    request: Request,
    user: User = Depends(internal_staff),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> DashboardOut:
    return services.build_dashboard(session, user, now, request.app.state.settings.payment_terms_days)
