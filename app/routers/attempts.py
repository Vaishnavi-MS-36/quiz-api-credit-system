from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    AttemptStatus,
    Quiz,
    QuizAttempt,
    TransactionType,
    User,
)
from app.schemas import (
    AttemptResponse,
    AttemptStartResponse,
    SubmitRequest,
    SubmitResponse,
)
from app.services.credits import InsufficientCreditsError, apply_transaction, lock_user

router = APIRouter(tags=["Attempts"])


@router.post(
    "/quizzes/{quiz_id}/start",
    response_model=AttemptStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Lock the user row first: concurrent "start" calls by the same user queue up here.
    user = lock_user(db, current_user.id)

    quiz = db.scalar(
        select(Quiz).where(Quiz.id == quiz_id).options(selectinload(Quiz.questions))
    )
    if quiz is None or not quiz.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    if not quiz.questions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Quiz has no questions yet"
        )

    open_attempt = db.scalar(
        select(QuizAttempt.id).where(
            QuizAttempt.user_id == user.id,
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    )
    if open_attempt is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have an in-progress attempt (id={open_attempt}) for this quiz",
        )

    attempt = QuizAttempt(
        user_id=user.id,
        quiz_id=quiz.id,
        staked_amount=quiz.stake_amount,
        status=AttemptStatus.IN_PROGRESS,
    )
    db.add(attempt)
    db.flush()  # get attempt.id for the ledger row

    try:
        apply_transaction(
            db,
            user,
            TransactionType.STAKE,
            -quiz.stake_amount,
            attempt_id=attempt.id,
            description=f"Stake for quiz '{quiz.title}'",
        )
    except InsufficientCreditsError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits to stake for this quiz",
        )

    db.commit()
    return AttemptStartResponse(
        attempt_id=attempt.id,
        quiz_id=quiz.id,
        staked_amount=attempt.staked_amount,
        balance_after=user.credits,
        questions=quiz.questions,
    )


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitResponse)
def submit_attempt(
    attempt_id: int,
    payload: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Lock the attempt row: a second concurrent submit waits, then sees status != IN_PROGRESS.
    attempt = db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if attempt is None or attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Attempt already submitted"
        )

    quiz = db.scalar(
        select(Quiz).where(Quiz.id == attempt.quiz_id).options(selectinload(Quiz.questions))
    )
    questions = {q.id: q for q in quiz.questions}

    seen: set[int] = set()
    score = 0
    for answer in payload.answers:
        question = questions.get(answer.question_id)
        if question is None:
            raise HTTPException(
                status_code=422,
                detail=f"Question {answer.question_id} does not belong to this quiz",
            )
        if answer.question_id in seen:
            raise HTTPException(
                status_code=422, detail=f"Duplicate answer for question {answer.question_id}"
            )
        if answer.selected_option >= len(question.options):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid option for question {answer.question_id}",
            )
        seen.add(answer.question_id)
        if answer.selected_option == question.correct_option:
            score += 1

    total = len(questions)
    passed = total > 0 and score * 100 >= quiz.pass_percentage * total
    percentage = (score * 100 // total) if total else 0

    attempt.score = score
    attempt.total_questions = total
    attempt.answers = {str(a.question_id): a.selected_option for a in payload.answers}
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.status = AttemptStatus.PASSED if passed else AttemptStatus.FAILED

    reward = 0
    user = lock_user(db, current_user.id)
    if passed:
        reward = quiz.reward_amount
        apply_transaction(
            db,
            user,
            TransactionType.REWARD,
            reward,
            attempt_id=attempt.id,
            description=f"Reward for passing quiz '{quiz.title}'",
        )

    db.commit()
    return SubmitResponse(
        attempt_id=attempt.id,
        status=attempt.status,
        score=score,
        total_questions=total,
        percentage=percentage,
        pass_percentage=quiz.pass_percentage,
        passed=passed,
        staked_amount=attempt.staked_amount,
        reward_amount=reward,
        balance=user.credits,
    )


@router.get("/attempts", response_model=list[AttemptResponse])
def my_attempts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.id.desc())
    ).all()


@router.get("/attempts/{attempt_id}", response_model=AttemptResponse)
def get_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None or attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt