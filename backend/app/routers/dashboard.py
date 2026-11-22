"""Management dashboard (finance and managers)."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import services
from app.auth import get_now, get_payment_terms_days, get_session, internal_staff
from app.models import User
from app.schemas import DashboardOut

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    user: User = Depends(internal_staff),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
    payment_terms_days: int = Depends(get_payment_terms_days),
) -> DashboardOut:
    return services.build_dashboard(session, user, now, payment_terms_days)
