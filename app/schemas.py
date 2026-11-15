from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import AttemptStatus, TransactionType, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    credits: int
    created_at: datetime
    # ---------- Quiz & Question schemas ----------


class QuestionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_option: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_options(self):
        if any(not o.strip() for o in self.options):
            raise ValueError("Options must not be empty")
        if len(set(o.strip().lower() for o in self.options)) != len(self.options):
            raise ValueError("Options must be unique")
        if self.correct_option >= len(self.options):
            raise ValueError("correct_option must be a valid index into options")
        return self


class QuestionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=1000)
    options: list[str] | None = Field(default=None, min_length=2, max_length=6)
    correct_option: int | None = Field(default=None, ge=0)


class QuestionAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    text: str
    options: list[str]
    correct_option: int


class QuestionPublicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    options: list[str]


class QuizCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    stake_amount: int = Field(gt=0)
    reward_amount: int = Field(gt=0)
    pass_percentage: int = Field(default=60, ge=1, le=100)
    is_active: bool = True
    questions: list[QuestionCreate] = Field(default_factory=list)


class QuizUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    stake_amount: int | None = Field(default=None, gt=0)
    reward_amount: int | None = Field(default=None, gt=0)
    pass_percentage: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


class QuizSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    stake_amount: int
    reward_amount: int
    pass_percentage: int
    is_active: bool
    question_count: int


class QuizAdminDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    stake_amount: int
    reward_amount: int
    pass_percentage: int
    is_active: bool
    created_at: datetime
    questions: list[QuestionAdminResponse]


class QuizPublicDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    stake_amount: int
    reward_amount: int
    pass_percentage: int
    questions: list[QuestionPublicResponse]

    # ---------- Attempt schemas ----------


class AnswerItem(BaseModel):
    question_id: int
    selected_option: int = Field(ge=0)


class SubmitRequest(BaseModel):
    answers: list[AnswerItem] = Field(min_length=1, max_length=100)


class AttemptStartResponse(BaseModel):
    attempt_id: int
    quiz_id: int
    staked_amount: int
    balance_after: int
    questions: list[QuestionPublicResponse]


class SubmitResponse(BaseModel):
    attempt_id: int
    status: AttemptStatus
    score: int
    total_questions: int
    percentage: int
    pass_percentage: int
    passed: bool
    staked_amount: int
    reward_amount: int
    balance: int


class AttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    staked_amount: int
    status: AttemptStatus
    score: int | None
    total_questions: int | None
    started_at: datetime
    submitted_at: datetime | None

    # ---------- Credit schemas ----------


class BalanceResponse(BaseModel):
    credits: int


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: TransactionType
    amount: int
    balance_after: int
    attempt_id: int | None
    description: str | None
    created_at: datetime


class PurchaseRequest(BaseModel):
    amount: int = Field(gt=0, le=10000, description="Number of credits to buy")
    payment_method: str = Field(
        default="mock_card_success",
        pattern="^(mock_card_success|mock_card_decline)$",
        description="mock_card_success approves the payment, mock_card_decline declines it",
    )


class PurchaseResponse(BaseModel):
    payment_status: str
    transaction_id: int
    credits_purchased: int
    balance: int