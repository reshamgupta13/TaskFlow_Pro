export type TaskColumn = 'backlog' | 'in_progress' | 'review' | 'done';

export interface Task {
  id: string;
  title: string;
  description: string;
  column: TaskColumn;
  position: number;
  duration_days: number;
  planned_start: string;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
  updated_at: string;
  is_blocked: boolean;
  blocking_task_ids: string[];
  has_regression_warning: boolean;
  warning_message: string | null;
  is_critical_path: boolean;
  prerequisites: string[];
  dependents: string[];
}

export interface Dependency {
  task_id: string;
  prerequisite_id: string;
  source: 'manual' | 'ai';
  created_at: string;
}

export interface AISuggestion {
  id: string;
  task_id: string;
  prerequisite_id: string;
  rationale: string;
  confidence: number;
  status: 'pending' | 'accepted' | 'rejected';
  created_at: string;
  task_title?: string;
  prerequisite_title?: string;
}

export interface AIMetrics {
  total_suggestions: number;
  accepted: number;
  rejected: number;
  pending: number;
  acceptance_rate: number;
}

export interface BoardStats {
  total_tasks: number;
  ready_tasks: number;
  blocked_tasks: number;
  done_tasks: number;
  in_progress_tasks: number;
  total_duration_days: number;
  critical_path_length: number;
}

export interface BoardResponse {
  tasks: Task[];
  dependencies: Dependency[];
  critical_path: string[];
  pending_suggestions: AISuggestion[];
  stats: BoardStats;
}
