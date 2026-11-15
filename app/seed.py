from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.models import Transaction, TransactionType, User, UserRole
from app.security import hash_password


def seed_admin() -> None:
    """Create the admin user once, if ADMIN_EMAIL and ADMIN_PASSWORD are set."""
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return
    email = settings.ADMIN_EMAIL.lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            return
        admin = User(
            email=email,
            full_name="Admin",
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            credits=settings.SIGNUP_BONUS_CREDITS,
        )
        db.add(admin)
        try:
            db.flush()
            db.add(
                Transaction(
                    user_id=admin.id,
                    type=TransactionType.SIGNUP_BONUS,
                    amount=settings.SIGNUP_BONUS_CREDITS,
                    balance_after=admin.credits,
                    description="Welcome bonus",
                )
            )
            db.commit()
        except IntegrityError:
            db.rollback()  # another instance created it first