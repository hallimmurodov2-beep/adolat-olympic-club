from __future__ import annotations
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Activity, ActivityItem, Classroom, Problem, StoredFile, Submission, SubmissionFile, Topic, User
from .access import competing, grade_visible, phase, released_material, staff


def columns(record: Any, *names: str) -> dict:
    return {name: getattr(record, name) for name in names}


def file_data(file: StoredFile) -> dict:
    return columns(file, 'id', 'filename', 'media_type', 'size', 'created_at')


def problem_snapshot(problem: Problem) -> dict:
    return columns(problem, 'title', 'statement', 'subtopic', 'hints', 'solution', 'examples', 'difficulty', 'source', 'year', 'tags', 'format', 'topic_id', 'version')


def problem_data(db: Session, user: User, problem: Problem) -> dict:
    result = problem_snapshot(problem)
    hints, solution = released_material(db, user, problem)
    if not hints:
        result['hints'] = {}
    if not solution:
        result['solution'] = {}
    result.update(columns(problem, 'id', 'classroom_id', 'published', 'created_at', 'updated_at'))
    room = db.get(Classroom, problem.classroom_id)
    result['subject_id'] = room.subject_id
    result['topic'] = db.get(Topic, problem.topic_id).name if problem.topic_id else {}
    result['files'] = [file_data(f) for f in db.scalars(select(StoredFile).where(StoredFile.target_kind == 'problem', StoredFile.target_id == problem.id))]
    return result


def activity_data(db: Session, activity: Activity) -> dict:
    data = columns(activity, 'id', 'classroom_id', 'kind', 'title', 'description', 'starts_at', 'ends_at', 'duration_minutes', 'status', 'edit_version', 'results_published', 'announcement', 'created_at')
    room = db.get(Classroom, activity.classroom_id)
    data.update(phase=phase(activity), subject_id=room.subject_id, classroom_name=room.name)
    return data


def item_data(db: Session, user: User, item: ActivityItem, activity: Activity) -> dict:
    data = columns(item, 'id', 'problem_id', 'position', 'points', 'rubric', 'released_at', 'hints_released', 'solution_released')
    snapshot = dict(item.snapshot)
    can_reveal = staff(user) or (not competing(db, user) and (activity.kind != 'competition' or (activity.results_published and phase(activity) == 'ended')))
    if not staff(user) and (not item.hints_released or not can_reveal):
        snapshot['hints'] = {}
    if not staff(user) and (not item.solution_released or not can_reveal):
        snapshot['solution'] = {}
    snapshot.pop('file_ids', None)
    data['problem'] = snapshot
    # Attachments are statement-only. Solutions/hints must use their protected text fields.
    files_query = select(StoredFile).where(StoredFile.target_kind == 'problem', StoredFile.target_id == item.problem_id)
    if 'file_ids' in item.snapshot:
        files_query = files_query.where(StoredFile.id.in_(item.snapshot['file_ids']))
    data['files'] = [file_data(f) for f in db.scalars(files_query)]
    return data


def submission_data(db: Session, user: User, submission: Submission, detail: bool = False) -> dict:
    item = db.get(ActivityItem, submission.activity_item_id)
    activity = db.get(Activity, item.activity_id)
    data = columns(submission, 'id', 'activity_item_id', 'user_id', 'group_id', 'attempt', 'created_at', 'language', 'group_revision')
    released = grade_visible(user, submission, activity)
    data.update(status=submission.status if released else 'submitted', score=submission.score if released else None,
        feedback=submission.feedback if released else {}, criterion_scores=submission.criterion_scores if released else [],
        released=(activity.results_published and phase(activity) == 'ended' and submission.status != 'submitted') if activity.kind == 'competition' else submission.released, grade_version=submission.grade_version if staff(user) else 0,
        graded_at=submission.graded_at if released else None, points=item.points, rubric=item.rubric,
        problem_title=item.snapshot['title'], activity_title=activity.title, activity_id=activity.id,
        classroom_id=activity.classroom_id, author_name=db.get(User, submission.user_id).display_name, kind=activity.kind)
    if detail:
        data['content'] = submission.content
        data['problem'] = item_data(db, user, item, activity)['problem']
        data['files'] = [file_data(f) for f in db.scalars(select(StoredFile).join(SubmissionFile, SubmissionFile.file_id == StoredFile.id).where(SubmissionFile.submission_id == submission.id))]
    return data
