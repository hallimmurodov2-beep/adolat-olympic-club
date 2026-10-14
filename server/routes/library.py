from __future__ import annotations
import unicodedata
from fastapi import APIRouter, Query
from sqlalchemy import func, select, update
from ..errors import require
from ..models import Classroom, Problem, ProblemSet, SetItem, now_ms
from ..schemas import ProblemInput, SetInput
from ..security import Actor, Db
from ..services.access import classroom_access, classroom_ids, problem_access, staff
from ..services.events import audit, emit
from ..services.serialize import columns, problem_data
from .classrooms import validate_topic

router = APIRouter(prefix='/api', tags=['Problem library'])


def search_text(body: ProblemInput) -> str:
    parts = [*body.title.values(), *body.statement.values(), *body.subtopic.values(), body.source, *body.tags]
    return unicodedata.normalize('NFKC', ' '.join(parts)).casefold()


@router.get('/problems')
def list_problems(db: Db, user: Actor, classroom_id: str | None = None, subject_id: str | None = None, topic_id: str | None = None,
                  difficulty: int | None = Query(None, ge=1, le=5), q: str = Query('', max_length=200), page: int = Query(1, ge=1), limit: int = Query(30, ge=1, le=100)):
    ids = classroom_ids(db, user)
    if classroom_id:
        classroom_access(db, user, classroom_id)
        ids = [classroom_id]
    query = select(Problem).where(Problem.classroom_id.in_(ids))
    if user.role == 'student':
        # The library exposes only explicitly published problems; activity-private tasks stay private.
        query = query.where(Problem.published.is_(True))
    if subject_id:
        query = query.join(Classroom).where(Classroom.subject_id == subject_id)
    if topic_id:
        query = query.where(Problem.topic_id == topic_id)
    if difficulty:
        query = query.where(Problem.difficulty == difficulty)
    if q.strip():
        query = query.where(Problem.search_text.contains(unicodedata.normalize('NFKC', q.strip()).casefold(), autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    records = db.scalars(query.order_by(Problem.updated_at.desc()).offset((page - 1) * limit).limit(limit))
    # No full statements or hidden material in search results.
    items = []
    for record in records:
        data = problem_data(db, user, record)
        for key in ('statement', 'hints', 'solution', 'examples'):
            data.pop(key, None)
        items.append(data)
    return {'items': items, 'total': total, 'page': page, 'limit': limit}


@router.post('/problems', status_code=201)
def create_problem(body: ProblemInput, db: Db, user: Actor):
    room = classroom_access(db, user, body.classroom_id, write=True)
    validate_topic(db, body.topic_id, room.subject_id)
    data = body.model_dump(exclude={'version'})
    problem = Problem(**data, author_id=user.id, search_text=search_text(body))
    db.add(problem)
    db.flush()
    emit(db, 'library', problem.id, classroom_id=room.id)
    audit(db, user.id, 'problem.created', problem.id)
    return problem_data(db, user, problem)


@router.get('/problems/{problem_id}')
def get_problem(problem_id: str, db: Db, user: Actor):
    return problem_data(db, user, problem_access(db, user, problem_id))


@router.put('/problems/{problem_id}')
def edit_problem(problem_id: str, body: ProblemInput, db: Db, user: Actor):
    problem = problem_access(db, user, problem_id, write=True)
    require(problem.classroom_id == body.classroom_id, 'cannot_move_problem', 409)
    room = db.get(Classroom, problem.classroom_id)
    validate_topic(db, body.topic_id, room.subject_id)
    require(body.version is not None, 'revision_required', 422)
    values = body.model_dump(exclude={'version'})
    values.update(version=Problem.version + 1, updated_at=now_ms(), search_text=search_text(body))
    changed = db.execute(update(Problem).where(Problem.id == problem.id, Problem.version == body.version).values(**values))
    require(changed.rowcount == 1, 'conflict', 409)
    db.refresh(problem)
    emit(db, 'library', problem.id, classroom_id=room.id)
    audit(db, user.id, 'problem.updated', problem.id)
    return problem_data(db, user, problem)


@router.get('/sets')
def list_sets(db: Db, user: Actor, classroom_id: str | None = None):
    require(staff(user))
    ids = classroom_ids(db, user)
    if classroom_id:
        classroom_access(db, user, classroom_id, write=True)
        ids = [classroom_id]
    result = []
    for problem_set in db.scalars(select(ProblemSet).where(ProblemSet.classroom_id.in_(ids)).order_by(ProblemSet.created_at.desc())):
        data = columns(problem_set, 'id', 'classroom_id', 'title', 'description')
        data['problem_ids'] = list(db.scalars(select(SetItem.problem_id).where(SetItem.set_id == problem_set.id).order_by(SetItem.position)))
        result.append(data)
    return result


@router.post('/sets', status_code=201)
def create_set(body: SetInput, db: Db, user: Actor):
    classroom_access(db, user, body.classroom_id, write=True)
    require(len(set(body.problem_ids)) == len(body.problem_ids), 'duplicate_problems', 422)
    for problem_id in body.problem_ids:
        problem = problem_access(db, user, problem_id, write=True)
        require(problem.classroom_id == body.classroom_id, 'invalid_problem', 422)
    problem_set = ProblemSet(classroom_id=body.classroom_id, title=body.title, description=body.description)
    db.add(problem_set)
    db.flush()
    for position, problem_id in enumerate(body.problem_ids):
        db.add(SetItem(set_id=problem_set.id, problem_id=problem_id, position=position))
    audit(db, user.id, 'set.created', problem_set.id)
    return {'id': problem_set.id}


@router.post('/sets/{set_id}/clone', status_code=201)
def clone_set(set_id: str, db: Db, user: Actor):
    """Same-classroom copy, new identity; existing set membership and work untouched."""
    source=db.get(ProblemSet,set_id)
    require(source is not None, 'not_found', 404)
    room=classroom_access(db,user,source.classroom_id,write=True)
    require(room.active, 'classroom_archived', 409)
    problems=list(db.scalars(select(SetItem).where(SetItem.set_id==source.id).order_by(SetItem.position)))
    require(bool(problems), 'invalid_input', 422)
    copy=ProblemSet(classroom_id=source.classroom_id,title=dict(source.title), description=dict(source.description))
    db.add(copy); db.flush()
    for item in problems:
        require(db.scalar(select(Problem.id).where(Problem.id==item.problem_id,Problem.classroom_id==source.classroom_id)) is not None,'invalid_problem',422)
        db.add(SetItem(set_id=copy.id,problem_id=item.problem_id,position=item.position))
    audit(db,user.id,'set.cloned',copy.id,{'source_id':source.id})
    return {'id':copy.id}
