from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import AttemptStatus, QuestionType, TestActivityType, TestStatus

TestState = Literal["DRAFT", "UPCOMING", "OPEN", "CLOSED"]

# ---------------------------------------------------------------------------- admin editor


class TestCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    book_id: uuid.UUID | None = None
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    duration_minutes: int = Field(default=15, ge=1, le=600)
    max_score: int | None = Field(default=None, ge=1, le=1000, description="Empty = value from settings")
    passing_score: int = Field(default=0, ge=0, le=1000)
    attempts_allowed: int = Field(default=1, ge=1, le=10)
    shuffle_questions: bool = True
    shuffle_options: bool = True

    @model_validator(mode="after")
    def _times(self) -> TestCreateIn:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class TestUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    book_id: uuid.UUID | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    max_score: int | None = Field(default=None, ge=1, le=1000)
    passing_score: int | None = Field(default=None, ge=0, le=1000)
    attempts_allowed: int | None = Field(default=None, ge=1, le=10)
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None


class OptionIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    is_correct: bool = False


class QuestionIn(BaseModel):
    type: QuestionType = QuestionType.SINGLE_CHOICE
    text: str = Field(min_length=1, max_length=2000)
    points: int = Field(default=1, ge=1, le=100)
    explanation: str | None = Field(default=None, max_length=2000)
    options: list[OptionIn] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def _correct_answers(self) -> QuestionIn:
        correct = sum(1 for option in self.options if option.is_correct)
        if self.type == QuestionType.SINGLE_CHOICE and correct != 1:
            raise ValueError("single-choice question needs exactly one correct option")
        if self.type == QuestionType.MULTIPLE_CHOICE and correct < 1:
            raise ValueError("multiple-choice question needs at least one correct option")
        texts = [option.text.strip().lower() for option in self.options]
        if len(set(texts)) != len(texts):
            raise ValueError("options must be different")
        return self


class QuestionsIn(BaseModel):
    questions: list[QuestionIn] = Field(min_length=1, max_length=200)


class OptionAdminOut(BaseModel):
    id: uuid.UUID
    text: str
    is_correct: bool


class QuestionAdminOut(BaseModel):
    id: uuid.UUID
    type: QuestionType
    text: str
    points: int
    explanation: str | None
    options: list[OptionAdminOut]


class TestAdminOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    book_id: uuid.UUID | None
    book_title: str | None
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    max_score: int
    passing_score: int
    attempts_allowed: int
    shuffle_questions: bool
    shuffle_options: bool
    status: TestStatus
    state: TestState
    question_count: int
    participant_count: int
    published_at: datetime | None
    rank_bonus_awarded: bool
    created_at: datetime
    event_id: uuid.UUID | None = None
    certificate_background: bool = False


class TestAdminDetailOut(TestAdminOut):
    questions: list[QuestionAdminOut]


class TestResultRow(BaseModel):
    attempt_id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    faculty: str | None
    course: int | None
    group_name: str | None
    attempt_number: int
    status: AttemptStatus
    score: int | None
    correct_count: int | None
    question_count: int
    passed: bool | None
    started_at: datetime
    submitted_at: datetime | None
    duration_seconds: int | None
    signals: int
    place: int | None


class TestResultsOut(BaseModel):
    test: TestAdminOut
    participants: int
    passed: int
    average_score: float | None
    items: list[TestResultRow]


class AttemptAnswerOut(BaseModel):
    question: str
    selected: list[str]
    correct: list[str]
    is_correct: bool | None
    answered_at: datetime | None


class ActivityOut(BaseModel):
    type: TestActivityType
    at: datetime
    details: dict[str, Any] | None


class AttemptDetailOut(BaseModel):
    attempt_id: uuid.UUID
    member: str
    status: AttemptStatus
    score: int | None
    started_at: datetime
    deadline_at: datetime
    submitted_at: datetime | None
    answers: list[AttemptAnswerOut]
    activity: list[ActivityOut]


# ---------------------------------------------------------------------------- members


class MyAttemptOut(BaseModel):
    attempt_number: int
    status: AttemptStatus
    score: int | None
    correct_count: int | None
    question_count: int
    submitted_at: datetime | None


class TestOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    book_id: uuid.UUID | None
    book_title: str | None
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    max_score: int
    passing_score: int
    attempts_allowed: int
    question_count: int
    state: TestState
    attempts: list[MyAttemptOut]
    best_score: int | None
    in_progress: bool
    can_start: bool
    review_available: bool


class OptionOut(BaseModel):
    id: uuid.UUID
    text: str


class QuestionOut(BaseModel):
    id: uuid.UUID
    type: QuestionType
    text: str
    points: int
    options: list[OptionOut]


class AttemptOut(BaseModel):
    """A running attempt. Correct answers are never part of it."""

    attempt_id: uuid.UUID
    test_id: uuid.UUID
    title: str
    attempt_number: int
    started_at: datetime
    deadline_at: datetime
    server_now: datetime
    questions: list[QuestionOut]
    answers: dict[uuid.UUID, list[uuid.UUID]]


class AnswerIn(BaseModel):
    question_id: uuid.UUID
    option_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class SubmitIn(BaseModel):
    # Optional final answers (saved before grading). Anything else the client sends, such as a
    # score, is not part of this model and is ignored.
    answers: list[AnswerIn] | None = Field(default=None, max_length=200)


class AnswerSavedOut(BaseModel):
    saved: bool = True
    server_now: datetime


class AttemptResultOut(BaseModel):
    attempt_id: uuid.UUID
    status: AttemptStatus
    score: int
    max_score: int
    passing_score: int
    passed: bool
    correct_count: int
    question_count: int
    points_awarded: int
    submitted_at: datetime | None
    attempts_left: int
    review_available_at: datetime


class ActivityEventIn(BaseModel):
    type: TestActivityType
    client_time: AwareDatetime | None = None
    details: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _small_details(self) -> ActivityEventIn:
        if self.details is not None and len(str(self.details)) > 500:
            raise ValueError("details too large")
        return self


class ActivityIn(BaseModel):
    events: list[ActivityEventIn] = Field(min_length=1, max_length=30)


class ReviewOptionOut(BaseModel):
    id: uuid.UUID
    text: str
    is_correct: bool
    selected: bool


class ReviewQuestionOut(BaseModel):
    id: uuid.UUID
    type: QuestionType
    text: str
    points: int
    explanation: str | None
    is_correct: bool
    points_awarded: int
    options: list[ReviewOptionOut]


class ReviewOut(BaseModel):
    test_id: uuid.UUID
    title: str
    score: int
    max_score: int
    correct_count: int
    question_count: int
    place: int | None
    participants: int
    questions: list[ReviewQuestionOut]
