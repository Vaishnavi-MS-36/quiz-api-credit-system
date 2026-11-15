from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction, TransactionType, User


class InsufficientCreditsError(Exception):
    pass


def lock_user(db: Session, user_id: int) -> User:
    """Load the user row with SELECT ... FOR UPDATE, always with fresh data."""
    return db.execute(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def apply_transaction(
    db: Session,
    user: User,
    tx_type: TransactionType,
    amount: int,
    attempt_id: int | None = None,
    description: str | None = None,
) -> Transaction:
    """Change the balance and write the ledger row. `user` must already be locked.
    The caller commits, so everything lands in one DB transaction."""
    new_balance = user.credits + amount
    if new_balance < 0:
        raise InsufficientCreditsError()
    user.credits = new_balance
    tx = Transaction(
        user_id=user.id,
        type=tx_type,
        amount=amount,
        balance_after=new_balance,
        attempt_id=attempt_id,
        description=description,
    )
    db.add(tx)
    return tx