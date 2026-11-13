"""Authentication and workspace authorization helpers."""

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import AuthSession, Comment, Creator, Post, User, UserCreator


_bearer = HTTPBearer(auto_error=False)


def _session_ttl_days() -> int:
    try:
        return max(1, min(int(os.getenv("AUTH_SESSION_DAYS", "7")), 90))
    except ValueError:
        return 7


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> str:
    """Create an opaque bearer token while storing only its hash."""
    now = datetime.utcnow()
    db.query(AuthSession).filter(
        AuthSession.user_id == user.user_id,
        AuthSession.expires_at <= now,
    ).delete(synchronize_session=False)

    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.user_id,
            token_hash=_token_hash(token),
            expires_at=now + timedelta(days=_session_ttl_days()),
        )
    )
    db.commit()
    return token


def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthSession:
    """Resolve a valid bearer token to its database session."""
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_session = db.query(AuthSession).filter(
        AuthSession.token_hash == _token_hash(credentials.credentials)
    ).first()
    if not auth_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if auth_session.expires_at <= datetime.utcnow():
        db.delete(auth_session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth_session


def get_current_user(
    auth_session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.user_id == auth_session.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_creator_access(db: Session, user: User, creator_id: int) -> Creator:
    creator = db.query(Creator).join(
        UserCreator, UserCreator.creator_id == Creator.creator_id
    ).filter(
        Creator.creator_id == creator_id,
        UserCreator.user_id == user.user_id,
    ).first()
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found",
        )
    return creator


def require_post_access(db: Session, user: User, post_id: int) -> Post:
    post = db.query(Post).join(
        UserCreator, UserCreator.creator_id == Post.creator_id
    ).filter(
        Post.post_id == post_id,
        UserCreator.user_id == user.user_id,
    ).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )
    return post


def require_comment_access(db: Session, user: User, comment_id: int) -> Comment:
    comment = db.query(Comment).join(Post).join(
        UserCreator, UserCreator.creator_id == Post.creator_id
    ).filter(
        Comment.comment_id == comment_id,
        UserCreator.user_id == user.user_id,
    ).first()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    return comment
