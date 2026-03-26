"""User key and credits endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import session
from app.core.environment import env
from app.domains.user.service.key_service import KeyService
from app.shared.auth import auth_must
from app.shared.auth.user_auth import V1UserAuth

router = APIRouter(tags=["User Key"])


class KeyResponse(BaseModel):
    value: str
    api_url: str = ""
    warning_code: str | None = None
    warning_text: str | None = None


class KeyIn(BaseModel):
    value: str


class CreditsOut(BaseModel):
    credits: int


@router.get("/user/key", name="get active key", response_model=KeyResponse)
def get_key(
    db_session: Session = Depends(session),
    auth: V1UserAuth = Depends(auth_must),
):
    """Get the user's active cloud API key."""
    key = KeyService.get_active_key(auth.id, db_session)
    return KeyResponse(
        value=key.value if key else "",
        api_url=env("litellm_url", ""),
    )


@router.put("/user/key", name="save key", response_model=KeyResponse)
def put_key(
    data: KeyIn,
    db_session: Session = Depends(session),
    auth: V1UserAuth = Depends(auth_must),
):
    """Save or update the user's cloud API key."""
    key = KeyService.save_key(auth.id, data.value, db_session)
    return KeyResponse(
        value=key.value,
        api_url=env("litellm_url", ""),
    )


@router.get("/user/current_credits", name="get current credits", response_model=CreditsOut)
def get_credits(
    db_session: Session = Depends(session),
    auth: V1UserAuth = Depends(auth_must),
):
    """Get the user's current credits balance."""
    credits = KeyService.get_current_credits(auth.id, db_session)
    return CreditsOut(credits=credits)
