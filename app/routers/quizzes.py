from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Question, Quiz, User
from app.schemas import (
    QuestionAdminResponse,
    QuestionCreate,
    QuestionUpdate,
    QuizAdminDetailResponse,
    QuizCreate,
    QuizPublicDetailResponse,
    QuizSummaryResponse,
    QuizUpdate,
)

router = APIRouter(tags=["Quizzes"])


def _get_quiz_or_404(db: Session, quiz_id: int) -> Quiz:
    quiz = db.scalar(
        select(Quiz).where(Quiz.id == quiz_id).options(selectinload(Quiz.questions))
    )
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    return quiz


# ---------------- User-facing ----------------


@router.get("/quizzes", response_model=list[QuizSummaryResponse])
def list_quizzes(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(
        select(Quiz, func.count(Question.id))
        .outerjoin(Question, Question.quiz_id == Quiz.id)
        .where(Quiz.is_active.is_(True))
        .group_by(Quiz.id)
        .order_by(Quiz.id)
    ).all()
    return [
        QuizSummaryResponse(
            id=q.id,
            title=q.title,
            description=q.description,
            stake_amount=q.stake_amount,
            reward_amount=q.reward_amount,
            pass_percentage=q.pass_percentage,
            is_active=q.is_active,
            question_count=count,
        )
        for q, count in rows
    ]


@router.get("/quizzes/{quiz_id}", response_model=QuizPublicDetailResponse)
def get_quiz(quiz_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    quiz = _get_quiz_or_404(db, quiz_id)
    if not quiz.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    return quiz  # public schema hides correct answers


# ---------------- Admin: quizzes ----------------


@router.post(
    "/admin/quizzes",
    response_model=QuizAdminDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_quiz(payload: QuizCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    quiz = Quiz(
        title=payload.title.strip(),
        description=payload.description,
        stake_amount=payload.stake_amount,
        reward_amount=payload.reward_amount,
        pass_percentage=payload.pass_percentage,
        is_active=payload.is_active,
        questions=[
            Question(
                text=q.text.strip(),
                options=[o.strip() for o in q.options],
                correct_option=q.correct_option,
            )
            for q in payload.questions
        ],
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz


@router.get("/admin/quizzes", response_model=list[QuizAdminDetailResponse])
def admin_list_quizzes(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(
        select(Quiz).options(selectinload(Quiz.questions)).order_by(Quiz.id)
    ).all()


@router.get("/admin/quizzes/{quiz_id}", response_model=QuizAdminDetailResponse)
def admin_get_quiz(quiz_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return _get_quiz_or_404(db, quiz_id)


@router.patch("/admin/quizzes/{quiz_id}", response_model=QuizAdminDetailResponse)
def update_quiz(
    quiz_id: int,
    payload: QuizUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    quiz = _get_quiz_or_404(db, quiz_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None and field != "description":
            continue
        setattr(quiz, field, value)
    db.commit()
    db.refresh(quiz)
    return quiz


@router.delete("/admin/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(quiz_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    quiz = _get_quiz_or_404(db, quiz_id)
    if quiz.attempts:
        # Keep history intact: quizzes that were attempted are deactivated, not deleted.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Quiz has attempts and cannot be deleted. Deactivate it instead (is_active=false).",
        )
    db.delete(quiz)
    db.commit()


# ---------------- Admin: questions ----------------


@router.post(
    "/admin/quizzes/{quiz_id}/questions",
    response_model=QuestionAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_question(
    quiz_id: int,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    quiz = _get_quiz_or_404(db, quiz_id)
    question = Question(
        quiz_id=quiz.id,
        text=payload.text.strip(),
        options=[o.strip() for o in payload.options],
        correct_option=payload.correct_option,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.patch(
    "/admin/quizzes/{quiz_id}/questions/{question_id}",
    response_model=QuestionAdminResponse,
)
def update_question(
    quiz_id: int,
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    question = db.scalar(
        select(Question).where(Question.id == question_id, Question.quiz_id == quiz_id)
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    data = payload.model_dump(exclude_unset=True)
    new_options = data.get("options", question.options)
    new_correct = data.get("correct_option", question.correct_option)

    if any(not o.strip() for o in new_options):
        raise HTTPException(status_code=422, detail="Options must not be empty")
    if len({o.strip().lower() for o in new_options}) != len(new_options):
        raise HTTPException(status_code=422, detail="Options must be unique")
    if new_correct >= len(new_options):
        raise HTTPException(
            status_code=422, detail="correct_option must be a valid index into options"
        )

    if "text" in data and data["text"] is not None:
        question.text = data["text"].strip()
    question.options = [o.strip() for o in new_options]
    question.correct_option = new_correct
    db.commit()
    db.refresh(question)
    return question


@router.delete(
    "/admin/quizzes/{quiz_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_question(
    quiz_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    question = db.scalar(
        select(Question).where(Question.id == question_id, Question.quiz_id == quiz_id)
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    db.delete(question)
    db.commit()