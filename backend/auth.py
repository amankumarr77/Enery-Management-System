"""
Authentication & Authorization
JWT-based auth with role-based access control.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from src.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger("emsjb.auth")

# ── Password hashing ───────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── OAuth2 scheme ───────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ── User helpers ────────────────────────────────────────────

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(db: Session, username: str, password: str,
                email: Optional[str] = None, full_name: Optional[str] = None,
                role: str = "TRADER") -> models.User:
    user = models.User(
        username=username,
        hashed_password=hash_password(password),
        email=email,
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"User created: {username} (role={role})")
    return user


# ── Dependencies ────────────────────────────────────────────

async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """
    Get current user from JWT token if provided.
    Returns None if no token (allows unauthenticated access for dev).
    """
    if token is None:
        return None

    payload = decode_token(token)
    if payload is None:
        return None

    username: str = payload.get("sub")
    if username is None:
        return None

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None

    return user


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """
    Get current user — returns None if not authenticated.
    For commercial use, switch this to raise HTTPException(401).
    """
    if token is None:
        return None

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


def require_role(required_roles: list):
    """Dependency that checks user has one of the required roles."""
    async def role_checker(
        user: Optional[models.User] = Depends(get_current_user),
    ):
        if user is None:
            return None  # Allow unauthenticated in dev mode
        if user.role not in required_roles and user.role.value not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_roles}",
            )
        return user
    return role_checker


def ensure_default_admin(db: Session):
    """Create a default admin user if no users exist."""
    user_count = db.query(models.User).count()
    if user_count == 0:
        create_user(
            db,
            username="admin",
            password="admin123",
            email="admin@emsjb.local",
            full_name="System Admin",
            role="ADMIN",
        )
        logger.info("Default admin user created: admin / admin123")
