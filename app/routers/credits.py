from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Transaction, TransactionType, User
from app.schemas import (
    BalanceResponse,
    PurchaseRequest,
    PurchaseResponse,
    TransactionResponse,
)
from app.services.credits import apply_transaction, lock_user

router = APIRouter(prefix="/credits", tags=["Credits"])


@router.get("/balance", response_model=BalanceResponse)
def get_balance(current_user: User = Depends(get_current_user)):
    return BalanceResponse(credits=current_user.credits)


@router.get("/transactions", response_model=list[TransactionResponse])
def get_transactions(
    type: TransactionType | None = Query(default=None, description="Filter by type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Transaction).where(Transaction.user_id == current_user.id)
    if type is not None:
        query = query.where(Transaction.type == type)
    query = query.order_by(Transaction.id.desc()).limit(limit).offset(offset)
    return db.scalars(query).all()


@router.post("/purchase", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
def purchase_credits(
    payload: PurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Mock payment gateway: a declined card never touches the balance or the ledger.
    if payload.payment_method == "mock_card_decline":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment declined",
        )

    user = lock_user(db, current_user.id)
    tx = apply_transaction(
        db,
        user,
        TransactionType.PURCHASE,
        payload.amount,
        description=f"Purchased {payload.amount} credits (mock payment)",
    )
    db.commit()
    return PurchaseResponse(
        payment_status="succeeded",
        transaction_id=tx.id,
        credits_purchased=payload.amount,
        balance=user.credits,
    )