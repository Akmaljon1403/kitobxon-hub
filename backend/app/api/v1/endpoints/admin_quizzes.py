"""Admin Panel: test editor, publishing, closing and results."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.core.errors import NotFoundError
from app.models import Event, Test
from app.schemas.common import Page
from app.schemas.quiz import (
    AttemptDetailOut,
    ImageKeyOut,
    ImportOut,
    OptionAdminOut,
    QuestionAdminOut,
    QuestionsIn,
    TestAdminDetailOut,
    TestAdminOut,
    TestCreateIn,
    TestResultRow,
    TestResultsOut,
    TestUpdateIn,
)
from app.security.permissions import Perm
from app.services import certificate_backgrounds, test_import
from app.services import quizzes as quiz_service
from app.services.storage import get_storage

router = APIRouter(prefix="/admin", tags=["admin: tests"])
TestViewer = Annotated[CurrentUser, Depends(require_permissions(Perm.TEST_VIEW))]
TestCreator = Annotated[CurrentUser, Depends(require_permissions(Perm.TEST_CREATE))]
TestEditor = Annotated[CurrentUser, Depends(require_permissions(Perm.TEST_EDIT))]
TestDeleter = Annotated[CurrentUser, Depends(require_permissions(Perm.TEST_DELETE))]
TestPublisher = Annotated[CurrentUser, Depends(require_permissions(Perm.TEST_PUBLISH))]


async def _tests_out(db, tests: list[Test]) -> list[TestAdminOut]:
    ids = [test.id for test in tests]
    questions = await quiz_service.question_counts(db, ids)
    participants = await quiz_service.participant_counts(db, ids)
    titles = await quiz_service.book_titles(db, {test.book_id for test in tests if test.book_id})
    return [
        TestAdminOut(
            id=test.id,
            title=test.title,
            description=test.description,
            book_id=test.book_id,
            book_title=titles.get(test.book_id) if test.book_id else None,
            starts_at=test.starts_at,
            ends_at=test.ends_at,
            duration_minutes=test.duration_minutes,
            max_score=test.max_score,
            passing_score=test.passing_score,
            attempts_allowed=test.attempts_allowed,
            shuffle_questions=test.shuffle_questions,
            shuffle_options=test.shuffle_options,
            status=test.status,
            state=quiz_service.state(test),
            question_count=questions.get(test.id, 0),
            participant_count=participants.get(test.id, 0),
            published_at=test.published_at,
            rank_bonus_awarded=test.rank_bonus_awarded_at is not None,
            created_at=test.created_at,
            event_id=test.event_id,
            certificate_background=test.certificate_background_key is not None,
        )
        for test in tests
    ]


async def _detail(db, test: Test) -> TestAdminDetailOut:
    base = (await _tests_out(db, [test]))[0]
    questions = await quiz_service.load_questions(db, test.id)
    return TestAdminDetailOut(
        **base.model_dump(),
        questions=[
            QuestionAdminOut(
                id=question.id,
                type=question.type,
                text=question.text,
                points=question.points,
                explanation=question.explanation,
                options=[OptionAdminOut(id=o.id, text=o.text, is_correct=o.is_correct) for o in options],
                image_key=question.image_key,
            )
            for question, options in questions
        ],
    )


@router.get("/tests", response_model=Page[TestAdminOut], summary="All tests")
async def list_tests(
    _: TestViewer,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TestAdminOut]:
    tests, total = await quiz_service.list_tests_admin(db, limit=limit, offset=offset)
    return Page[TestAdminOut](items=await _tests_out(db, tests), total=total, limit=limit, offset=offset)


@router.post("/tests", response_model=TestAdminDetailOut, status_code=status.HTTP_201_CREATED, summary="Create a test")
async def create_test(payload: TestCreateIn, current: TestCreator, db: DbSession) -> TestAdminDetailOut:
    test = await quiz_service.create_test(db, actor_id=current.user.id, data=payload.model_dump())
    return await _detail(db, test)


@router.get("/tests/{test_id}", response_model=TestAdminDetailOut, summary="Test with questions and answers")
async def get_test(test_id: uuid.UUID, _: TestViewer, db: DbSession) -> TestAdminDetailOut:
    return await _detail(db, await quiz_service.get_test(db, test_id))


@router.patch("/tests/{test_id}", response_model=TestAdminDetailOut, summary="Change test settings")
async def update_test(
    test_id: uuid.UUID, payload: TestUpdateIn, current: TestEditor, db: DbSession
) -> TestAdminDetailOut:
    test = await quiz_service.update_test(
        db, actor_id=current.user.id, test_id=test_id, changes=payload.model_dump(exclude_unset=True)
    )
    return await _detail(db, test)


@router.put("/tests/{test_id}/questions", response_model=TestAdminDetailOut, summary="Save all questions")
async def save_questions(
    test_id: uuid.UUID, payload: QuestionsIn, current: TestEditor, db: DbSession
) -> TestAdminDetailOut:
    test = await quiz_service.replace_questions(
        db,
        actor_id=current.user.id,
        test_id=test_id,
        questions=[question.model_dump() for question in payload.questions],
    )
    return await _detail(db, test)


@router.post("/tests/{test_id}/publish", response_model=TestAdminDetailOut, summary="Publish to members")
async def publish(test_id: uuid.UUID, current: TestPublisher, db: DbSession) -> TestAdminDetailOut:
    return await _detail(db, await quiz_service.publish_test(db, actor_id=current.user.id, test_id=test_id))


@router.post("/tests/{test_id}/unpublish", response_model=TestAdminDetailOut, summary="Back to draft (no attempts yet)")
async def unpublish(test_id: uuid.UUID, current: TestPublisher, db: DbSession) -> TestAdminDetailOut:
    return await _detail(db, await quiz_service.unpublish_test(db, actor_id=current.user.id, test_id=test_id))


@router.post("/tests/{test_id}/close", response_model=TestAdminDetailOut, summary="Close now and award place bonuses")
async def close(test_id: uuid.UUID, current: TestPublisher, db: DbSession) -> TestAdminDetailOut:
    return await _detail(db, await quiz_service.close_test(db, actor_id=current.user.id, test_id=test_id))


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a test without results")
async def delete_test(test_id: uuid.UUID, current: TestDeleter, db: DbSession) -> Response:
    await quiz_service.delete_test(db, actor_id=current.user.id, test_id=test_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tests/{test_id}/results", response_model=TestResultsOut, summary="Attempts, scores and signals")
async def results(test_id: uuid.UUID, _: TestViewer, db: DbSession) -> TestResultsOut:
    test, items = await quiz_service.results(db, test_id)
    finished = [item for item in items if item["score"] is not None]
    return TestResultsOut(
        test=(await _tests_out(db, [test]))[0],
        participants=len({item["user_id"] for item in items}),
        passed=len({item["user_id"] for item in items if item["passed"]}),
        average_score=round(sum(item["score"] for item in finished) / len(finished), 1) if finished else None,
        items=[TestResultRow(**item) for item in items],
    )


@router.get("/tests/{test_id}/results.csv", summary="Results as CSV (opens in Excel)")
async def results_csv(test_id: uuid.UUID, _: TestViewer, db: DbSession) -> Response:
    filename, content = await quiz_service.export_csv(db, test_id)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/test-attempts/{attempt_id}", response_model=AttemptDetailOut, summary="One attempt: answers and signals")
async def attempt_detail(attempt_id: uuid.UUID, _: TestViewer, db: DbSession) -> AttemptDetailOut:
    return AttemptDetailOut(**await quiz_service.attempt_detail(db, attempt_id))


# ---------------------------------------------------------------------------- import and question pictures


@router.post(
    "/tests/{test_id}/import",
    response_model=ImportOut,
    summary="Read questions from a TXT, Word or PDF file (not saved: the editor shows them first)",
)
async def import_questions(
    test_id: uuid.UUID, _: TestEditor, db: DbSession, file: Annotated[UploadFile, File()]
) -> ImportOut:
    test = await quiz_service.get_test(db, test_id)
    data = await file.read(test_import.MAX_BYTES + 1)
    questions, warnings = await test_import.import_file(test.id, file.filename or "", data)
    return ImportOut(questions=questions, warnings=warnings)


@router.post("/tests/{test_id}/question-images", response_model=ImageKeyOut, summary="Upload a question's picture")
async def upload_question_image(
    test_id: uuid.UUID, _: TestEditor, db: DbSession, file: Annotated[UploadFile, File()]
) -> ImageKeyOut:
    test = await quiz_service.get_test(db, test_id)
    data = await file.read(test_import.MAX_IMAGE_BYTES + 1)
    prepared = test_import.prepare_image(data)
    key = test_import.image_key(test.id)
    await get_storage().put(key, prepared, "image/jpeg")
    return ImageKeyOut(image_key=key)


@router.get("/tests/{test_id}/question-images", summary="A question's picture", response_class=Response)
async def question_image(test_id: uuid.UUID, key: str, _: TestViewer, db: DbSession) -> Response:
    test = await quiz_service.get_test(db, test_id)
    if not key.startswith(f"tests/{test.id}/") or ".." in key:
        raise NotFoundError("IMAGE_NOT_FOUND", "Rasm topilmadi.")
    return Response(content=await get_storage().get(key), media_type="image/jpeg")


# ---------------------------------------------------------------------------- the test's own certificate design


@router.put(
    "/tests/{test_id}/certificate-background",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Upload the test's certificate design (admins until the start, the super admin until it ends)",
)
async def set_certificate_background(
    test_id: uuid.UUID, current: TestEditor, db: DbSession, file: Annotated[UploadFile, File()]
) -> Response:
    test = await quiz_service.get_test(db, test_id)
    data = await file.read(certificate_backgrounds.MAX_BYTES + 1)
    await certificate_backgrounds.set_background(
        db, actor_id=current.user.id, super_admin="SUPER_ADMIN" in current.roles, target=test, data=data
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/tests/{test_id}/certificate-background",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Back to the standard designs (the event's design, if it has one)",
)
async def remove_certificate_background(test_id: uuid.UUID, current: TestEditor, db: DbSession) -> Response:
    test = await quiz_service.get_test(db, test_id)
    await certificate_backgrounds.set_background(
        db, actor_id=current.user.id, super_admin="SUPER_ADMIN" in current.roles, target=test, data=None
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/tests/{test_id}/certificate-preview.png",
    summary="How the winners' certificate of this test will look (a sample)",
    response_class=Response,
)
async def certificate_preview(test_id: uuid.UUID, _: TestViewer, db: DbSession) -> Response:
    test = await quiz_service.get_test(db, test_id)
    if test.certificate_background_key is None and test.event_id is not None:
        event = await db.get(Event, test.event_id)
        if event is not None and event.certificate_background_key:
            return Response(content=await certificate_backgrounds.preview(db, event), media_type="image/png")
    return Response(content=await certificate_backgrounds.preview(db, test), media_type="image/png")
