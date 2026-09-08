"""短时管理员会话；密钥只在服务端校验，浏览器只持有 HttpOnly Cookie。"""

import hashlib
import hmac
import os
import time

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

SESSION_COOKIE = "jobflow_admin_session"
SESSION_TTL = 8 * 60 * 60
router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    token: str


def _admin_secret() -> str:
    return os.getenv("JOBFLOW_ADMIN_TOKEN") or os.getenv("REPORT_TRIGGER_TOKEN") or ""


def _signature(timestamp: str, secret: str) -> str:
    return hmac.new(secret.encode(), timestamp.encode(), hashlib.sha256).hexdigest()


def _valid_session(value: str | None) -> bool:
    secret = _admin_secret()
    if not secret or not value or "." not in value:
        return False
    timestamp, signature = value.split(".", 1)
    try:
        fresh = time.time() - int(timestamp) <= SESSION_TTL
    except ValueError:
        return False
    return fresh and hmac.compare_digest(signature, _signature(timestamp, secret))


def require_admin(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> None:
    if not _valid_session(session):
        raise HTTPException(status_code=401, detail="administrator session required")


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    secret = _admin_secret()
    if not secret or not hmac.compare_digest(payload.token, secret):
        raise HTTPException(status_code=401, detail="invalid administrator token")
    timestamp = str(int(time.time()))
    response.set_cookie(
        SESSION_COOKIE,
        f"{timestamp}.{_signature(timestamp, secret)}",
        max_age=SESSION_TTL,
        httponly=True,
        samesite="strict",
        secure=os.getenv("JOBFLOW_COOKIE_SECURE", "false").lower() == "true",
    )
    return {"status": "authenticated", "expires_in": SESSION_TTL}


@router.get("/session")
def session(_: None = Depends(require_admin)):
    return {"status": "authenticated"}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "signed_out"}
