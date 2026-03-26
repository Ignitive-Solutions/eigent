# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========

"""v1 Login - 1h access token, refresh token, rate limit."""

import time
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_babel import _
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session

from app.core import code
from app.core.database import session
from app.core.encrypt import password_verify
from app.core.environment import env
from app.model.user.user import LoginByPasswordIn, LoginResponse, Status, User
from app.shared.auth import create_access_token, create_refresh_token
from app.shared.auth.token_blacklist import blacklist_token
from app.shared.auth.user_auth import decode_refresh_token
from app.shared.exception import TokenException, UserException
from app.shared.middleware.rate_limit import login_rate_limiter

router = APIRouter(prefix="/user", tags=["V1 Login"])


@router.post("/dev_login", name="dev login (Swagger only)", include_in_schema=True)
async def dev_login(username: str | None = Form(default=None), password: str | None = Form(default=None)):
    """Debug-only login for Swagger Authorize. Accepts OAuth2 password form."""
    if env("debug", "") != "on":
        raise HTTPException(status_code=404)
    return {"access_token": create_access_token(1), "token_type": "bearer"}


@router.post("/auto-login", name="auto login for local mode")
async def auto_login(db_session: Session = Depends(session)) -> LoginResponse:
    """Auto login for fully local mode. Returns most recently active user or creates default."""
    user = User.by(
        User.status == Status.Normal,
        order_by=User.updated_at.desc(),
        limit=1,
        s=db_session,
    ).one_or_none()

    if not user:
        with db_session as s:
            try:
                user = User(
                    email="admin@local.eigent.ai",
                    username="admin",
                    nickname="Admin",
                    avatar="",
                    fullname="",
                    work_desc="",
                )
                s.add(user)
                s.commit()
                s.refresh(user)
                logger.info("Default admin user created", extra={"user_id": user.id})
            except Exception as e:
                s.rollback()
                logger.error("Failed to create default admin user", extra={"error": str(e)}, exc_info=True)
                raise UserException(code.error, _("Failed to create default user"))

    logger.info("Auto login successful", extra={"user_id": user.id, "email": user.email})
    return LoginResponse(token=create_access_token(user.id), email=user.email)


class RefreshTokenIn(BaseModel):
    refresh_token: str


@router.post("/login", name="login by email or password", dependencies=[login_rate_limiter])
async def by_password(data: LoginByPasswordIn, db_session: Session = Depends(session)) -> dict:
    """User login with email and password. Returns access_token (1h) and refresh_token (30d)."""
    user = User.by(User.email == data.email, s=db_session).one_or_none()
    if not user or not password_verify(data.password, user.password):
        raise UserException(code.password, _("Account or password error"))
    if user.status == Status.Block:
        raise UserException(code.error, _("Your account has been blocked."))
    if not user.is_active:
        raise UserException(code.error, _("Please activate your account via the email link."))

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email": user.email,
    }


@router.post("/refresh", name="refresh tokens", dependencies=[login_rate_limiter])
async def refresh(data: RefreshTokenIn, db_session: Session = Depends(session)) -> dict:
    """Exchange valid refresh_token for new access_token and refresh_token."""
    if not data.refresh_token:
        raise TokenException(code.token_need, _("Refresh token required"))
    user_id, jti, exp_ts = await decode_refresh_token(data.refresh_token)
    user = db_session.get(User, user_id)
    if not user:
        raise TokenException(code.token_invalid, _("User not found"))
    if user.status == Status.Block:
        raise UserException(code.error, _("Your account has been blocked."))
    if not user.is_active:
        raise UserException(code.error, _("Please activate your account via the email link."))
    if jti:
        ttl = max(0, exp_ts - int(time.time()))
        await blacklist_token(jti, ttl)
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email": user.email,
    }


# ==================== Google OAuth Login ====================

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def _google_login_credentials():
    client_id = env("GOOGLE_LOGIN_CLIENT_ID", "")
    client_secret = env("GOOGLE_LOGIN_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Set GOOGLE_LOGIN_CLIENT_ID and GOOGLE_LOGIN_CLIENT_SECRET.",
        )
    return client_id, client_secret


@router.get("/google-auth", name="Google OAuth login redirect")
async def google_auth(request: Request):
    """Redirect to Google OAuth consent screen."""
    client_id, _ = _google_login_credentials()

    callback_url = str(request.url_for("Google OAuth Callback"))
    if callback_url.startswith("http://"):
        callback_url = "https://" + callback_url[len("http://"):]

    authorize_url = (
        f"{_GOOGLE_AUTH_URL}?"
        f"client_id={client_id}"
        f"&redirect_uri={quote(callback_url, safe='')}"
        f"&response_type=code"
        f"&scope={'openid email profile'.replace(' ', '%20')}"
        f"&access_type=offline"
    )
    return RedirectResponse(authorize_url)


@router.get("/google-callback", name="Google OAuth Callback")
async def google_callback(request: Request, code: str | None = None, db_session: Session = Depends(session)):
    """Handle Google OAuth callback — exchange code, find/create user, redirect to Electron with JWT."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    client_id, client_secret = _google_login_credentials()
    callback_url = str(request.url_for("Google OAuth Callback"))
    if callback_url.startswith("http://"):
        callback_url = "https://" + callback_url[len("http://"):]

    # 1. Exchange code for Google access token
    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": callback_url,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_data = token_resp.json()
            google_access_token = token_data.get("access_token")
            if not google_access_token:
                logger.error("Google token exchange failed", extra={"response": token_data})
                raise HTTPException(status_code=502, detail="Google token exchange failed")
    except httpx.HTTPError as e:
        logger.error("Google token exchange error", extra={"error": str(e)})
        raise HTTPException(status_code=502, detail="Google token exchange failed")

    # 2. Fetch user info from Google
    try:
        async with httpx.AsyncClient() as client:
            userinfo_resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {google_access_token}"},
            )
            userinfo = userinfo_resp.json()
            google_email = userinfo.get("email")
            if not google_email:
                raise HTTPException(status_code=502, detail="Google did not return email")
    except httpx.HTTPError as e:
        logger.error("Google userinfo fetch error", extra={"error": str(e)})
        raise HTTPException(status_code=502, detail="Failed to fetch Google user info")

    # 3. Find or create user
    user = User.by(User.email == google_email, s=db_session).one_or_none()
    if not user:
        google_name = userinfo.get("name", "")
        google_picture = userinfo.get("picture", "")
        try:
            user = User(
                email=google_email,
                username=google_email.split("@")[0],
                nickname=google_name,
                fullname=google_name,
                avatar=google_picture,
                password=None,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            logger.info("User created via Google OAuth", extra={"user_id": user.id, "email": google_email})
        except Exception as e:
            db_session.rollback()
            logger.error("Failed to create user from Google OAuth", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create user account")

    if user.status == Status.Block:
        raise HTTPException(status_code=403, detail="Your account has been blocked.")

    # 4. Create JWT and redirect to Electron
    jwt_token = create_access_token(user.id)
    logger.info("Google OAuth login successful", extra={"user_id": user.id, "email": user.email})

    redirect_url = f"eigent://auth/callback?token={quote(jwt_token, safe='')}"
    return RedirectResponse(redirect_url)
