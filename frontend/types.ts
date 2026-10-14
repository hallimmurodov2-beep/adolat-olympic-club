export type Locale = 'ru' | 'en';
export type Role = 'admin' | 'teacher' | 'student';
export type Bi = Partial<Record<Locale, string>>;
export type Kind = 'assignment' | 'session' | 'competition';
export type Phase = 'draft' | 'upcoming' | 'active' | 'ended';
export type WorkLanguage = 'written' | 'python' | 'cpp';
export type ReviewStatus = 'submitted' | 'reviewed' | 'revision_requested';
export interface User {
    id: string;
    display_name: string;
    email: string;
    role: Role;
    locale: Locale;
    active: boolean;
}
export interface ClubSettings {
    name: Bi;
    timezone: string;
}
export interface Auth {
    user: User;
    csrf: string;
    settings: ClubSettings;
    server_now: number;
}
export interface Topic {
    id: string;
    subject_id: string;
    name: Bi;
}
export interface Subject {
    id: string;
    name: Bi;
    topics: Topic[];
}
export interface Member {
    id: string;
    display_name: string;
    active?: boolean;
}
export interface Classroom {
    id: string;
    name: Bi;
    description: Bi;
    subject_id: string;
    teacher_id: string;
    teacher_name: string;
    active: boolean;
    member_count: number;
    created_at: number;
}
export interface Announcement {
    id: string;
    body: Bi;
    created_at: number;
    author_name: string;
}
export interface Attachment {
    id: string;
    filename: string;
    media_type: string;
    size: number;
    created_at: number;
}
export interface Resource {
    id: string;
    title: Bi;
    body: Bi;
    url: string | null;
    topic_id: string | null;
    files: Attachment[];
    created_at: number;
}
export interface ClassroomDetail extends Classroom {
    members: Member[];
    announcements: Announcement[];
    resources: Resource[];
    activities: Activity[];
}
export interface ProblemContent {
    title: Bi;
    statement: Bi;
    subtopic: Bi;
    hints: Bi;
    solution: Bi;
    examples: Bi;
    difficulty: number;
    source: string;
    year: number | null;
    tags: string[];
    format: 'written' | 'code';
    topic_id: string | null;
    version: number;
}
export interface Problem extends ProblemContent {
    id: string;
    classroom_id: string;
    published: boolean;
    subject_id: string;
    topic: Bi;
    files: Attachment[];
    updated_at: number;
    created_at: number;
}
export interface ProblemPage {
    items: Problem[];
    total: number;
    page: number;
    limit: number;
}
export interface ProblemSet {
    id: string;
    classroom_id: string;
    title: Bi;
    description: Bi;
    problem_ids: string[];
}
export interface Criterion {
    name: Bi;
    max: number;
}
export interface Activity {
    id: string;
    classroom_id: string;
    classroom_name: Bi;
    subject_id: string;
    kind: Kind;
    title: Bi;
    description: Bi;
    starts_at: number | null;
    ends_at: number | null;
    duration_minutes: number;
    status: 'draft' | 'published' | 'live' | 'ended';
    edit_version: number;
    phase: Phase;
    results_published: boolean;
    announcement: Bi;
    created_at: number;
}
export interface ActivityItem {
    id: string;
    problem_id: string;
    position: number;
    points: number;
    rubric: Criterion[];
    released_at: number | null;
    hints_released: boolean;
    solution_released: boolean;
    problem: ProblemContent;
    files: Attachment[];
}
export interface HelpRequest {
    id: string;
    user_id: string;
    body: string;
    resolved: boolean;
    created_at: number;
    author_name: string;
}
export interface ActivityDetail extends Activity {
    items: ActivityItem[];
    submissions: Submission[];
    help_requests: HelpRequest[];
    participant_count: number;
    participants?: Member[];
    server_now: number;
}
export interface Work {
    content: string;
    language: WorkLanguage;
    revision: number;
    updated_at: number | null;
    files?: Attachment[];
    updated_by?: string;
}
export interface Submission {
    id: string;
    activity_item_id: string;
    user_id: string;
    group_id: string | null;
    attempt: number;
    created_at: number;
    language: WorkLanguage;
    group_revision: number | null;
    status: ReviewStatus;
    score: number | null;
    criterion_scores: number[];
    feedback: Bi;
    released: boolean;
    grade_version: number;
    graded_at: number | null;
    points: number;
    rubric: Criterion[];
    problem_title: Bi;
    activity_title: Bi;
    activity_id: string;
    classroom_id: string;
    author_name: string;
    kind: Kind;
    content?: string;
    problem?: ProblemContent;
    files?: Attachment[];
    grade_history?: GradeHistory[];
}
export interface GradeHistory {
    version: number;
    score: number;
    criterion_scores: number[];
    feedback: Bi;
    status: ReviewStatus;
    released: boolean;
    created_at: number;
    teacher_name: string;
}
export interface Group {
    id: string;
    classroom_id: string;
    activity_item_id: string;
    name: string;
    shared: boolean;
    created_at: number;
    members: Member[];
    revision: number;
    updated_at: number;
    problem_title: Bi;
    activity_id: string;
}
export interface GroupComment {
    id: string;
    body: string;
    created_at: number;
    author_name: string;
    author_role: Role;
}
export interface Revision {
    revision: number;
    content: string;
    language: WorkLanguage;
    created_at: number;
    author_name: string;
}
export interface GroupDetail extends Group {
    item: ActivityItem;
    phase: Phase;
    document: Work;
    can_edit: boolean;
    comments: GroupComment[];
    comments_next_cursor: string | null;
    revisions: Revision[];
    files: Attachment[];
}
export interface Notice {
    id: string;
    kind: string;
    title: Bi;
    link: string;
    read: boolean;
    created_at: number;
}
export interface Dashboard {
    server_now: number;
    classrooms: Classroom[];
    upcoming: Activity[];
    recent_activities: Activity[];
    feedback: Submission[];
    pending_reviews: number | null;
    attempts: number;
    reviewed: number;
    notifications_unread: number;
    active_competition: Activity | null;
}
export interface TopicProgress {
    id: string;
    name: Bi;
    subject_id: string;
    attempted: number;
    reviewed: number;
    score: number;
    possible: number;
}
export interface StudentProgress {
    id: string;
    name: string;
    assigned: number;
    attempted: number;
    reviewed: number;
    completed: number;
    score: number;
    possible: number;
}
export interface Progress {
    attempts: number;
    attempted: number;
    completed: number;
    reviewed: number;
    score: number;
    possible: number;
    topics: TopicProgress[];
    students: StudentProgress[];
    timeline: {
        date: string;
        attempted: number;
        reviewed: number;
    }[];
    difficulty: {
        id: string;
        title: Bi;
        activity_id: string;
        reviewed: number;
        score: number;
        possible: number;
    }[];
    competition_history: Activity[];
    feedback: Submission[];
}
export interface Invitation {
    id: string;
    email: string;
    role: 'teacher' | 'student';
    classroom_id: string | null;
    expires_at: number;
    accepted_at: number | null;
}
export interface InvitationPreview {
    email: string;
    role: 'teacher' | 'student';
    classroom_name: Bi;
    expires_at: number;
}
export interface InviteCreated {
    id: string;
    link: string;
    expires_at: number;
}
export interface Audit {
    id: number;
    action: string;
    entity_id: string;
    created_at: number;
    actor_name: string;
}
export interface ChangeEvent {
    kind: string;
    entity_id: string;
    server_now: number;
}
export interface MathJaxApi {
    startup?: {
        promise: Promise<void>;
    };
    typesetPromise?: (elements?: Element[]) => Promise<void>;
    typesetClear?: (elements?: Element[]) => void;
}
declare global {
    interface Window {
        MathJax?: MathJaxApi;
        Prism?: {
            highlightAllUnder: (element: Element) => void;
            highlightElement: (element: Element) => void;
        };
    }
}
