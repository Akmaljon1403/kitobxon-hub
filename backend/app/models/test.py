"""Knowledge tests about books: tests, questions, options, attempts, answers and activity signals.

Correct answers (``TestOption.is_correct``) never leave the backend before an attempt is
submitted. Scores are computed only on the server, and the server clock decides deadlines.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import AttemptStatus, QuestionType, TestActivityType, TestStatus


class Test(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __test__ = False  # tell pytest this is not a test class
    __tablename__ = "tests"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="dates_order"),
        CheckConstraint("duration_minutes BETWEEN 1 AND 600", name="duration_range"),
        CheckConstraint("max_score > 0", name="max_score_positive"),
        CheckConstraint("passing_score BETWEEN 0 AND max_score", name="passing_score_range"),
        CheckConstraint("attempts_allowed BETWEEN 1 AND 10", name="attempts_range"),
        Index("ix_tests_status_starts_at", "status", "starts_at"),
        Index("ix_tests_book_id", "book_id"),
    )

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    book_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"))
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    season_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    duration_minutes: Mapped[int] = mapped_column(Integer)
    # Points that enter the score ledger for a perfect result (default comes from settings).
    max_score: Mapped[int] = mapped_column(Integer)
    passing_score: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    attempts_allowed: Mapped[int] = mapped_column(Integer, default=1, server_default=sql_text("1"))
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql_text("true"))
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql_text("true"))
    status: Mapped[TestStatus] = mapped_column(
        enum_column(TestStatus), default=TestStatus.DRAFT, server_default=TestStatus.DRAFT.value
    )
    published_at: Mapped[datetime | None] = mapped_column()
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Set once the 1st/2nd/3rd place bonuses have been awarded after the test closed.
    rank_bonus_awarded_at: Mapped[datetime | None] = mapped_column()
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class TestQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __test__ = False
    __tablename__ = "test_questions"
    __table_args__ = (
        CheckConstraint("points > 0", name="points_positive"),
        Index("ix_test_questions_test_id_sort_order", "test_id", "sort_order"),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    # New question types can be added to the enum without changing the table layout.
    type: Mapped[QuestionType] = mapped_column(
        enum_column(QuestionType), default=QuestionType.SINGLE_CHOICE, server_default=QuestionType.SINGLE_CHOICE.value
    )
    text: Mapped[str] = mapped_column(Text)
    points: Mapped[int] = mapped_column(Integer, default=1, server_default=sql_text("1"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    # Optional explanation shown to members only after the test has closed.
    explanation: Mapped[str | None] = mapped_column(Text)


class TestOption(UUIDPrimaryKeyMixin, Base):
    __test__ = False
    __tablename__ = "test_options"
    __table_args__ = (Index("ix_test_options_question_id", "question_id"),)

    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_questions.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))


class TestAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __test__ = False
    __tablename__ = "test_attempts"
    __table_args__ = (
        UniqueConstraint("test_id", "user_id", "attempt_number"),
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        CheckConstraint("deadline_at > started_at", name="deadline_order"),
        # A member can have only one unfinished attempt per test.
        Index(
            "uq_test_attempts_in_progress",
            "test_id",
            "user_id",
            unique=True,
            postgresql_where=sql_text("status = 'IN_PROGRESS'"),
        ),
        Index("ix_test_attempts_user_id", "user_id"),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[AttemptStatus] = mapped_column(
        enum_column(AttemptStatus), default=AttemptStatus.IN_PROGRESS, server_default=AttemptStatus.IN_PROGRESS.value
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # min(started_at + duration, test.ends_at), fixed by the server when the attempt starts.
    deadline_at: Mapped[datetime] = mapped_column()
    submitted_at: Mapped[datetime | None] = mapped_column()
    # Per-attempt randomised order of questions, and of options per question.
    question_order: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    option_order: Mapped[dict[str, Any]] = mapped_column(JSONB)
    correct_count: Mapped[int | None] = mapped_column(Integer)
    raw_score: Mapped[int | None] = mapped_column(Integer)
    raw_max: Mapped[int | None] = mapped_column(Integer)
    # Ledger-scale score: round(raw_score / raw_max * test.max_score).
    score: Mapped[int | None] = mapped_column(Integer)


class TestAnswer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __test__ = False
    __tablename__ = "test_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_attempts.id", ondelete="CASCADE"))
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_questions.id", ondelete="RESTRICT"))
    selected_option_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    # Filled in by the server when the attempt is graded.
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    points_awarded: Mapped[int | None] = mapped_column(Integer)


class TestActivityLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Suspicious-activity *signals* (focus lost, app hidden, ...). They are indicators, not proof."""

    __test__ = False
    __tablename__ = "test_activity_logs"
    __table_args__ = (Index("ix_test_activity_logs_attempt_id", "attempt_id"),)

    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_attempts.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_type: Mapped[TestActivityType] = mapped_column(enum_column(TestActivityType))
    client_time: Mapped[datetime | None] = mapped_column()
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
