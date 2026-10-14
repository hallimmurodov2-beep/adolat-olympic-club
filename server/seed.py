"""Explicit, original demonstration content. Never run automatically in production."""
from __future__ import annotations
from sqlalchemy import select
from .models import *
from .security import hash_password

SUBJECTS = {
    'math': {'ru': 'Математика', 'en': 'Mathematics'},
    'physics': {'ru': 'Физика', 'en': 'Physics'},
    'informatics': {'ru': 'Информатика', 'en': 'Informatics'},
}


def initialize(db):
    for slug, name in SUBJECTS.items():
        if db.get(Subject, slug) is None:
            db.add(Subject(id=slug, name=name))
    if db.get(ClubSettings, 1) is None:
        db.add(ClubSettings(id=1, name={'ru': 'Adolat Olympic Club', 'en': 'Adolat Olympic Club'}, timezone='UTC'))
    db.flush()


def seed_demo(db, password: str) -> dict[str, str]:
    from .services.serialize import problem_snapshot
    from .services.events import notify
    import unicodedata
    if len(password) < 12:
        raise ValueError('Demo password must contain at least 12 characters.')
    if db.scalar(select(User.id).where(User.email.like('%@demo.school.test')).limit(1)):
        raise ValueError('Demo data already exists. Use a fresh database; no existing work will be overwritten.')
    initialize(db)
    db.get(ClubSettings, 1).name = {'ru': 'Adolat Olympic Club · Демо', 'en': 'Adolat Olympic Club · Demo'}
    encoded = hash_password(password)
    people = [
        ('admin', 'Администратор клуба', 'admin'),
        ('teacher', 'Мария Волкова', 'teacher'),
        ('physics', 'Алексей Орлов', 'teacher'),
        ('student', 'София Каримова', 'student'),
        ('teammate', 'Артём Соколов', 'student'),
        ('other', 'Даниил Петров', 'student'),
    ]
    users = {}
    for handle, name, role in people:
        person = User(email=f'{handle}@demo.school.test', display_name=name, password_hash=encoded, role=role, locale='ru')
        db.add(person); db.flush(); users[handle] = person
    topic_names = {
        'math': [('Теория чисел', 'Number theory'), ('Комбинаторика', 'Combinatorics'), ('Геометрия', 'Geometry'), ('Алгебра', 'Algebra')],
        'physics': [('Механика', 'Mechanics'), ('Электромагнетизм', 'Electromagnetism'), ('Термодинамика', 'Thermodynamics'), ('Волны', 'Waves')],
        'informatics': [('Алгоритмы', 'Algorithms'), ('Структуры данных', 'Data structures'), ('Теория графов', 'Graph theory'), ('Динамическое программирование', 'Dynamic programming')],
    }
    rooms, topics = {}, {}
    descriptions = {
        'math': {'ru': 'Ищем закономерности, строим доказательства и обсуждаем красивые решения.', 'en': 'Find patterns, build proofs, and discuss elegant solutions.'},
        'physics': {'ru': 'От физической модели к точному решению. Теория, расчёты и эксперименты.', 'en': 'From a physical model to a precise solution. Theory, calculation, and experiments.'},
        'informatics': {'ru': 'Учимся объяснять алгоритмы, оценивать сложность и писать понятный код.', 'en': 'Explain algorithms, reason about complexity, and write clear code.'},
    }
    for subject in SUBJECTS:
        teacher = users['physics'] if subject == 'physics' else users['teacher']
        room = Classroom(subject_id=subject, teacher_id=teacher.id, name={'ru': SUBJECTS[subject]['ru'] + ' · 9–11 классы', 'en': SUBJECTS[subject]['en'] + ' · Grades 9–11'}, description=descriptions[subject])
        db.add(room); db.flush(); rooms[subject] = room
        for ru, en in topic_names[subject]:
            topic = Topic(subject_id=subject, name={'ru': ru, 'en': en}, created_by=teacher.id)
            db.add(topic); db.flush(); topics[en] = topic
        for handle in ['student', 'teammate'] if subject != 'physics' else ['student', 'other']:
            from .models import SubjectMembership
            db.add(SubjectMembership(subject_id=subject, user_id=users[handle].id, source='demo'))
            db.add(Membership(classroom_id=room.id, user_id=users[handle].id))
        db.add(Announcement(classroom_id=room.id, author_id=teacher.id, body={'ru': 'Это учебный пример рабочего пространства. Обсуждайте идеи, записывайте ход рассуждений и задавайте вопросы преподавателю.', 'en': 'This is a demonstration workspace. Discuss ideas, write down your reasoning, and ask your teacher questions.'}))
        db.add(Resource(classroom_id=room.id, title={'ru': 'Как оформить решение', 'en': 'How to present a solution'}, body={'ru': 'Сформулируйте идею. Обоснуйте каждый переход. Проверьте граничные случаи и сформулируйте ответ. В формулах используйте $\\LaTeX$.', 'en': 'State the idea. Justify each step. Check boundary cases and state the conclusion. Use $\\LaTeX$ for equations.'}))
    records = [
        ('math', 'Number theory', {'ru': 'Делимость соседних чисел', 'en': 'Divisibility of consecutive numbers'},
         {'ru': 'Найдите все натуральные числа $n$, для которых $n^2+3n+2$ делится на $6$. Считайте $n\\geq 1$. Обоснуйте ответ.', 'en': 'Find all positive integers $n$ for which $n^2+3n+2$ is divisible by $6$. Assume $n\\geq1$. Prove your answer.'},
         {'ru': 'Разложите выражение на множители и рассмотрите остатки по модулю $3$.', 'en': 'Factor the expression and consider the residues modulo $3$.'},
         {'ru': 'Имеем $(n+1)(n+2)$. Произведение соседних чисел всегда чётно. Оно делится на $3$ тогда и только тогда, когда $n\\not\\equiv0\\pmod3$. Поэтому подходят все положительные $n$, не кратные $3$.', 'en': 'We have $(n+1)(n+2)$. The product of consecutive integers is even. It is divisible by $3$ exactly when $n\\not\\equiv0\\pmod3$. Thus all positive integers not divisible by $3$ work.'}, 2, 'written'),
        ('math', 'Combinatorics', {'ru': 'Пять чисел — одна разность', 'en': 'Five numbers, one difference'},
         {'ru': 'Докажите, что среди любых пяти целых чисел найдутся два, разность которых делится на $4$.', 'en': 'Prove that among any five integers, two have a difference divisible by $4$.'},
         {'ru': 'Сколько существует остатков при делении на $4$?', 'en': 'How many residue classes are there modulo $4$?'},
         {'ru': 'Есть четыре класса остатков: $0,1,2,3$. По принципу Дирихле два из пяти чисел имеют одинаковый остаток. Их разность делится на $4$.', 'en': 'There are four residue classes: $0,1,2,3$. By the pigeonhole principle, two of the five integers have the same residue. Their difference is divisible by $4$.'}, 2, 'written'),
        ('math', 'Geometry', {'ru': 'Середины сторон треугольника', 'en': 'Midpoints of a triangle'},
         {'ru': 'В треугольнике $ABC$ точки $M$ и $N$ — середины сторон $AB$ и $AC$. Докажите, что $MN\\parallel BC$ и $MN=BC/2$.', 'en': 'In triangle $ABC$, points $M$ and $N$ are the midpoints of $AB$ and $AC$. Prove that $MN\\parallel BC$ and $MN=BC/2$.'},
         {'ru': 'Рассмотрите гомотетию с центром $A$ и коэффициентом $1/2$.', 'en': 'Consider a homothety centered at $A$ with scale factor $1/2$.'},
         {'ru': 'Гомотетия переводит $B$ в $M$, а $C$ в $N$. Образ прямой $BC$ параллелен ей, а длины уменьшаются вдвое.', 'en': 'The homothety maps $B$ to $M$ and $C$ to $N$. The image of line $BC$ is parallel to it, and all lengths are halved.'}, 1, 'written'),
        ('physics', 'Mechanics', {'ru': 'Два участка пути', 'en': 'Two parts of a journey'},
         {'ru': 'Первую половину пути велосипедист проехал со скоростью $v$, вторую — со скоростью $2v$. Найдите среднюю скорость за весь путь. Объясните, почему арифметическое среднее скоростей здесь не подходит.', 'en': 'A cyclist travels the first half of a journey at speed $v$ and the second half at $2v$. Find the average speed. Explain why the arithmetic mean of the speeds is not appropriate.'},
         {'ru': 'Выразите время на каждом участке через общую длину пути $S$.', 'en': 'Express the time spent on each half using the total distance $S$.'},
         {'ru': '$t=S/(2v)+S/(4v)=3S/(4v)$, поэтому $v_{\\text{ср}}=S/t=4v/3$. Время движения на участках неодинаково.', 'en': '$t=S/(2v)+S/(4v)=3S/(4v)$, so $v_{\\text{avg}}=S/t=4v/3$. The cyclist spends different amounts of time at the two speeds.'}, 2, 'written'),
        ('informatics', 'Algorithms', {'ru': 'Самый длинный возрастающий участок', 'en': 'Longest increasing segment'},
         {'ru': 'Дан массив из $n$ целых чисел, $1\\leq n\\leq 10^5$. Найдите длину самого длинного непрерывного строго возрастающего участка. Ввод: $n$, затем $n$ чисел. Вывод: искомая длина. Обоснуйте сложность алгоритма.', 'en': 'Given an array of $n$ integers, $1\\leq n\\leq 10^5$, find the length of its longest contiguous strictly increasing segment. Input: $n$, followed by $n$ integers. Output: the length. Explain the complexity of your algorithm.'},
         {'ru': 'При одном проходе храните длину текущего возрастающего участка.', 'en': 'Keep the current increasing segment length during a single scan.'},
         {'ru': 'Если $a_i>a_{i-1}$, увеличьте текущую длину, иначе присвойте ей $1$. Поддерживайте максимум. Сложность: $O(n)$ по времени, $O(1)$ дополнительной памяти при потоковом чтении.', 'en': 'If $a_i>a_{i-1}$, increment the current length; otherwise reset it to $1$. Maintain the maximum. This takes $O(n)$ time and $O(1)$ auxiliary space with streaming input.'}, 2, 'code'),
        ('informatics', 'Graph theory', {'ru': 'Связность небольшого графа', 'en': 'Connectivity of a small graph'},
         {'ru': 'Дан неориентированный граф с $n$ вершинами и $m$ рёбрами. Выведите число компонент связности. Ограничения: $1\\leq n\\leq10^4$, $0\\leq m\\leq10^5$. Ввод: $n$, $m$, затем пары концов рёбер (нумерация с $1$).', 'en': 'Given an undirected graph with $n$ vertices and $m$ edges, output its number of connected components. Constraints: $1\\leq n\\leq10^4$, $0\\leq m\\leq10^5$. Input: $n$, $m$, followed by the edge endpoints (numbered from $1$).'},
         {'ru': 'Запускайте обход из каждой ещё не посещённой вершины.', 'en': 'Start a traversal from each vertex that has not yet been visited.'},
         {'ru': 'Каждый новый запуск BFS или итеративного DFS находит одну компоненту. Всего требуется $O(n+m)$ времени и памяти.', 'en': 'Each new BFS or iterative DFS identifies one component. Total time and space are $O(n+m)$.'}, 3, 'code'),
    ]
    problems = []
    for subject, topic, title, statement, hints, solution, difficulty, format in records:
        search = unicodedata.normalize('NFKC', ' '.join([*title.values(), *statement.values()])).casefold()
        problem = Problem(classroom_id=rooms[subject].id, author_id=rooms[subject].teacher_id, topic_id=topics[topic].id, title=title, statement=statement, hints=hints, solution=solution, difficulty=difficulty, format=format, source='Adolat Olympic Club · original demo', tags=[], published=True, search_text=search)
        if format == 'code':
            problem.examples = {'ru': 'Ввод:\n5\n1 2 2 3 4\n\nВывод:\n3', 'en': 'Input:\n5\n1 2 2 3 4\n\nOutput:\n3'} if topic == 'Algorithms' else {'ru': 'Ввод:\n4 2\n1 2\n3 4\n\nВывод:\n2', 'en': 'Input:\n4 2\n1 2\n3 4\n\nOutput:\n2'}
        db.add(problem); db.flush(); problems.append(problem)
    at = now_ms()
    definitions = [
        ('math', 'assignment', {'ru': 'Остатки и принцип Дирихле', 'en': 'Residues and the pigeonhole principle'}, [0, 1], at - 86400000, at + 3 * 86400000, 'published'),
        ('math', 'session', {'ru': 'Мастерская доказательств', 'en': 'Proof workshop'}, [1, 2], at + 3600000, at + 7200000, 'draft'),
        ('physics', 'assignment', {'ru': 'Скорость, путь и время', 'en': 'Speed, distance, and time'}, [3], at - 3600000, at + 2 * 86400000, 'published'),
        ('informatics', 'assignment', {'ru': 'Один проход по массиву', 'en': 'A single pass through an array'}, [4], at - 3600000, at + 4 * 86400000, 'published'),
        ('math', 'competition', {'ru': 'Тренировочная олимпиада · тур 1', 'en': 'Mock olympiad · Round 1'}, [0, 2], at + 7 * 86400000, at + 7 * 86400000 + 7200000, 'published'),
    ]
    activity_items = []
    activities = []
    for subject, kind, title, indices, start, end, status in definitions:
        activity = Activity(classroom_id=rooms[subject].id, kind=kind, title=title, description={'ru': 'Учебный пример. Преподаватель проверяет решения вручную.', 'en': 'Demonstration activity. Solutions are reviewed manually by the teacher.'}, starts_at=start, ends_at=end, status=status, duration_minutes=60)
        db.add(activity); db.flush(); activities.append(activity)
        items = []
        for position, index in enumerate(indices):
            problem = problems[index]
            item = ActivityItem(activity_id=activity.id, problem_id=problem.id, snapshot=problem_snapshot(problem), position=position, points=7,
                rubric=[{'name': {'ru': 'Идея решения', 'en': 'Key idea'}, 'max': 2}, {'name': {'ru': 'Обоснование', 'en': 'Justification'}, 'max': 4}, {'name': {'ru': 'Ответ', 'en': 'Conclusion'}, 'max': 1}] if kind == 'assignment' and subject == 'math' else [])
            db.add(item); db.flush(); items.append(item)
        activity_items.append(items)
        if kind == 'competition':
            for handle in ('student', 'teammate'):
                db.add(Participant(activity_id=activity.id, user_id=users[handle].id))
    solution = '$(n+1)(n+2)$ всегда чётно. Если $n$ кратно $3$, ни один множитель не делится на $3$. В двух остальных случаях делится один из них. Ответ: $n\\not\\equiv0\\pmod3$.'
    for handle, item, reviewed in [('student', activity_items[0][0], True), ('teammate', activity_items[0][0], False)]:
        submission = Submission(activity_item_id=item.id, user_id=users[handle].id, owner_key='user:' + users[handle].id, client_id=uid(), request_hash='0'*64, attempt=1, content=solution, language='written', created_at=at-6*3600000,
            status='reviewed' if reviewed else 'submitted', score=7 if reviewed else None, criterion_scores=[2,4,1] if reviewed else [], feedback={'ru': 'Хорошее разбиение на случаи. Все переходы обоснованы.', 'en': 'A clear case analysis. Every step is justified.'} if reviewed else {}, released=reviewed, graded_by=users['teacher'].id if reviewed else None, graded_at=at-3*3600000 if reviewed else None, grade_version=1 if reviewed else 0)
        db.add(submission); db.flush(); db.add(SubmissionMember(submission_id=submission.id, user_id=users[handle].id))
        if reviewed:
            db.add(GradeRevision(submission_id=submission.id, teacher_id=users['teacher'].id, version=1, score=7, criterion_scores=[2,4,1], feedback=submission.feedback, status='reviewed', released=True))
            notify(db, [users[handle].id], 'grade_released', item.snapshot['title'], '/submissions/' + submission.id)
    group = Group(classroom_id=rooms['math'].id, activity_item_id=activity_items[0][1].id, name='Команда 01', shared=False)
    db.add(group); db.flush()
    db.add(GroupDocument(group_id=group.id, content='', revision=0))
    for handle in ('student', 'teammate'):
        db.add(GroupMember(group_id=group.id, user_id=users[handle].id))
        notify(db, [users[handle].id], 'group_assigned', {'ru': group.name, 'en': 'Team 01'}, '/groups/' + group.id)
    problem_set = ProblemSet(classroom_id=rooms['math'].id, title={'ru': 'Первые доказательства', 'en': 'First proofs'}, description={})
    db.add(problem_set); db.flush()
    for position, problem in enumerate(problems[:3]):
        db.add(SetItem(set_id=problem_set.id, problem_id=problem.id, position=position))
    db.flush()
    return {handle: user.email for handle, user in users.items()}
