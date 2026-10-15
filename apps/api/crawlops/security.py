import hashlib
import secrets
from datetime import UTC, timedelta

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from .config import settings
from .db import session
from .models import ApiToken, AuditEvent, Role, User, now


class Passwords:
    @staticmethod
    def hash(password):
        salt = secrets.token_hex(16)
        hashed = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
        return f"scrypt${salt}${hashed}"

    @staticmethod
    def verify(password, encoded):
        try:
            method, salt, expected = encoded.split("$")
            if method != "scrypt":
                return False
            actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
            return secrets.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False


passwords = Passwords()
bearer = HTTPBearer(auto_error=False)


def aware(dt):
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(auth: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(session)):
    if not auth:
        raise HTTPException(401, "Authentication required")
    token = db.scalar(select(ApiToken).where(ApiToken.digest == digest(auth.credentials)))
    if not token or (token.expires_at and aware(token.expires_at) <= now()):
        raise HTTPException(401, "Invalid or expired token")
    return db.get(User, token.user_id)


def operator(user=Depends(current_user)):
    if user.role not in {"admin", "operator"}:
        raise HTTPException(403, "Operator role required")
    return user


def admin(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    return user


def agent(auth: HTTPAuthorizationCredentials | None = Depends(bearer)):
    configured = settings().agent_token
    if not configured or not auth or not secrets.compare_digest(auth.credentials, configured):
        raise HTTPException(401, "Invalid agent credential")


def issue_token(db, user, name="session", permanent=False):
    raw = secrets.token_urlsafe(40)
    db.add(
        ApiToken(
            user_id=user.id,
            digest=digest(raw),
            name=name,
            expires_at=None if permanent else now() + timedelta(hours=settings().session_hours),
        )
    )
    db.commit()
    return raw


def audit(db, actor, action, target, details=None):
    db.add(AuditEvent(actor=actor, action=action, target=target, details=details or {}))


def cipher():
    if not settings().encryption_key:
        raise HTTPException(503, "Secret encryption is not configured")
    return Fernet(settings().encryption_key.encode())


def bootstrap(db):
    for role in ("admin", "operator", "viewer"):
        if not db.get(Role, role):
            db.add(Role(name=role))
    db.flush()
    if not db.scalar(select(User).where(User.email == settings().admin_email)):
        if len(settings().admin_password) < 12:
            raise RuntimeError("Set CRAWLOPS_ADMIN_PASSWORD to at least 12 characters")
        db.add(User(email=settings().admin_email, password_hash=passwords.hash(settings().admin_password)))
    db.commit()
