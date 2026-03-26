"""Key service — manages user cloud API keys and credits."""

from sqlmodel import Session, select

from app.model.user.key import Key, KeyStatus
from app.model.user.user import User


class KeyService:
    @staticmethod
    def get_active_key(user_id: int, db_session: Session) -> Key | None:
        """Get the user's active API key, if any."""
        stmt = (
            select(Key)
            .where(Key.user_id == user_id, Key.status == KeyStatus.active)
            .order_by(Key.created_at.desc())
            .limit(1)
        )
        return db_session.exec(stmt).first()

    @staticmethod
    def save_key(user_id: int, value: str, db_session: Session) -> Key:
        """Save or update the user's API key."""
        existing = KeyService.get_active_key(user_id, db_session)
        if existing:
            existing.value = value
            db_session.add(existing)
            db_session.commit()
            db_session.refresh(existing)
            return existing
        key = Key(user_id=user_id, value=value, status=KeyStatus.active)
        db_session.add(key)
        db_session.commit()
        db_session.refresh(key)
        return key

    @staticmethod
    def get_current_credits(user_id: int, db_session: Session) -> int:
        """Get the user's current credits balance from the user record."""
        user = db_session.get(User, user_id)
        if not user:
            return 0
        return getattr(user, "credits", 0) or 0
