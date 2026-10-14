import type { Bi } from './types.js';
export interface Page<T> {items: T[]; next_cursor: string | null;}
export interface Participation {items: {subject_id: string; name: Bi; active: boolean}[]; can_train: boolean; server_now: number;}
export type Outcome = 'not_started' | 'attempted' | 'revisit' | 'completed';
export interface TrainingItem {id: string; plan_id: string; title: string; url: string; status: Outcome; provider: string | null; problem_key: string | null; version: number; carried_from_id: string | null; created_at: number;}
export interface PracticeEntry {id: string; item_id: string; outcome: Outcome; assistance: string; reflection: Bi; next_step: Bi; created_at: number;}
export interface Plan {id: string; cycle_id: string; goal: Bi; review: Bi; next_step: Bi; context: {title: Bi; starts_at: number; ends_at: number; circle_id: string | null}; version: number; read_only: boolean; created_at: number; items: TrainingItem[]; entries: PracticeEntry[];}
export interface Cycle {id: string; circle_id: string | null; title: Bi; guidance: Bi; links: {title: string; url: string}[]; starts_at: number; ends_at: number; practice_starts_at: number | null; practice_ends_at: number | null; discussion_opens_at: number | null; mode: 'individual' | 'collaborative'; status: 'draft' | 'published' | 'cancelled'; version: number; can_manage: boolean; discussion_open: boolean; content_frozen: boolean; my_plan_id: string | null;}
export interface Circle {id: string; name: Bi; description: Bi; discoverable: boolean; archived: boolean; locked: boolean; version: number; my_role: string | null; my_status: string | null; member_count: number; can_manage: boolean; members: {id: string; display_name: string; role: string; status: string; transfer_consent: boolean}[];}
export interface Post {id: string; kind: string; body: Bi; created_at: number; author_name: string;}
export interface Profile {handle: string; rating: number | null; max_rating: number | null; rank: string | null; last_updated_at: number; profile_url: string;}
export interface CFAccount {id: string; handle: string; leaderboard_opt_in: boolean; approval_status: string; approval_method: string | null; approved_at: number | null; last_error: string | null; last_success_at: number | null; next_refresh_at: number; version: number; profile: Profile | null;}
export interface CFState {state: string; account: CFAccount | null; server_now: number;}
export interface LeaderRow extends Profile {position: number | null; school_approved: boolean; stale: boolean;}
export interface Leaderboard {items: LeaderRow[]; next_offset: number | null;}
export interface Contest {id: number; name: string; starts_at: number; duration_seconds: number; url: string;}
export interface Contests {items: Contest[]; last_updated_at: number | null; stale: boolean; error: string | null; available: boolean; source_url: string; server_now: number;}
export interface Report {id: string; circle_id: string; post_id: string | null; reason: string; detail: string; status: string; created_at: number; reported_post: {body: Bi; kind: string} | null;}
