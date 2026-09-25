import type { BoardResponse, TaskColumn, AIMetrics, AISuggestion } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export class ApiError extends Error {
  offending_loop?: string[];
  statusCode: number;

  constructor(message: string, statusCode: number, offending_loop?: string[]) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.offending_loop = offending_loop;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!res.ok) {
      let errorData: any = {};
      try {
        errorData = await res.json();
      } catch {
        // Non-JSON response
      }

      let errorMsg = `Request failed: ${res.statusText}`;
      let offendingLoop: string[] | undefined = undefined;

      if (errorData?.detail) {
        if (typeof errorData.detail === 'object') {
          errorMsg = errorData.detail.message || errorData.detail.error || errorMsg;
          offendingLoop = errorData.detail.offending_loop;
        } else {
          errorMsg = String(errorData.detail);
        }
      }

      throw new ApiError(errorMsg, res.status, offendingLoop);
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError((err as Error).message || 'Network error', 0);
  }
}

export const api = {
  getBoard: () => request<BoardResponse>('/board'),

  resetSeed: () => request<BoardResponse>('/board/reset-seed', { method: 'POST' }),

  createTask: (data: {
    title: string;
    description: string;
    duration_days: number;
    planned_start: string;
    column?: TaskColumn;
    prerequisite_ids?: string[];
  }) =>
    request<BoardResponse>('/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateTask: (
    id: string,
    data: {
      title?: string;
      description?: string;
      duration_days?: number;
      planned_start?: string;
    }
  ) =>
    request<BoardResponse>(`/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  moveTask: (id: string, column: TaskColumn, position?: number) =>
    request<BoardResponse>(`/tasks/${id}/move`, {
      method: 'PATCH',
      body: JSON.stringify({ column, position }),
    }),

  deleteTask: (id: string) =>
    request<BoardResponse>(`/tasks/${id}`, {
      method: 'DELETE',
    }),

  addDependency: (taskId: string, prerequisiteId: string) =>
    request<BoardResponse>('/dependencies', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, prerequisite_id: prerequisiteId }),
    }),

  removeDependency: (taskId: string, prerequisiteId: string) =>
    request<BoardResponse>(`/dependencies/${taskId}/${prerequisiteId}`, {
      method: 'DELETE',
    }),

  generateAISuggestions: () =>
    request<AISuggestion[]>('/ai/suggestions', { method: 'POST' }),

  acceptAISuggestion: (id: string) =>
    request<BoardResponse>(`/ai/suggestions/${id}/accept`, { method: 'POST' }),

  rejectAISuggestion: (id: string) =>
    request<AIMetrics>(`/ai/suggestions/${id}/reject`, { method: 'POST' }),

  getAIMetrics: () => request<AIMetrics>('/ai/metrics'),
};
