import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  AlertCircle,
  CheckCircle,
  Loader2,
} from 'lucide-react';
import type { BoardResponse, Task, TaskColumn } from './types';
import { api, ApiError } from './services/api';
import { Header } from './components/Header';
import { KanbanBoard } from './components/KanbanBoard';
import { TaskModal } from './components/TaskModal';
import { DependencyModal } from './components/DependencyModal';
import { AISuggestionDrawer } from './components/AISuggestionDrawer';
import { DAGVisualizerModal } from './components/DAGVisualizerModal';

interface Toast {
  id: string;
  type: 'error' | 'success';
  message: string;
}

export const App: React.FC = () => {
  const [board, setBoard] = useState<BoardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [criticalPathActive, setCriticalPathActive] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'ready' | 'blocked'>('all');

  // Modals & Panels
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);

  const [isDepsModalOpen, setIsDepsModalOpen] = useState(false);
  const [depsTargetTaskId, setDepsTargetTaskId] = useState<string | null>(null);

  const [isAIDrawerOpen, setIsAIDrawerOpen] = useState(false);
  const [isDAGModalOpen, setIsDAGModalOpen] = useState(false);

  // Toasts
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: 'error' | 'success' = 'error') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const loadBoard = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getBoard();
      setBoard(data);
    } catch (err: any) {
      addToast(`Failed to load board: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  // Optimistic Move Task
  const handleMoveTask = async (taskId: string, targetColumn: TaskColumn, newPosition?: number) => {
    if (!board) return;

    // Save previous state for rollback
    const previousBoard = board;

    // Optimistically update
    setBoard((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        tasks: prev.tasks.map((t) =>
          t.id === taskId ? { ...t, column: targetColumn } : t
        ),
      };
    });

    try {
      const updated = await api.moveTask(taskId, targetColumn, newPosition);
      setBoard(updated);
      addToast(`Moved task to ${targetColumn.replace('_', ' ')}`, 'success');
    } catch (err: any) {
      // Reconcile and roll back
      setBoard(previousBoard);
      addToast(err.message || 'Failed to move task', 'error');
    }
  };

  const handleCreateOrUpdateTask = async (data: any) => {
    try {
      let updated: BoardResponse;
      if (editingTask) {
        updated = await api.updateTask(editingTask.id, data);
        addToast(`Updated task "${data.title || editingTask.title}"`, 'success');
      } else {
        updated = await api.createTask(data);
        addToast(`Created task "${data.title}"`, 'success');
      }
      setBoard(updated);
    } catch (err: any) {
      addToast(err.message || 'Operation failed', 'error');
      throw err;
    }
  };

  const handleDeleteTask = async (id: string) => {
    try {
      const updated = await api.deleteTask(id);
      setBoard(updated);
      addToast(`Deleted task ${id}`, 'success');
    } catch (err: any) {
      addToast(err.message || 'Failed to delete task', 'error');
    }
  };

  const handleAddDependency = async (
    taskId: string,
    prereqId: string
  ): Promise<{ success: boolean; error?: string; loop?: string[] }> => {
    try {
      const updated = await api.addDependency(taskId, prereqId);
      setBoard(updated);
      addToast(`Added dependency: ${taskId} depends on ${prereqId}`, 'success');
      return { success: true };
    } catch (err: any) {
      if (err instanceof ApiError) {
        return {
          success: false,
          error: err.message,
          loop: err.offending_loop,
        };
      }
      return { success: false, error: err.message || 'Network error' };
    }
  };

  const handleRemoveDependency = async (taskId: string, prereqId: string) => {
    try {
      const updated = await api.removeDependency(taskId, prereqId);
      setBoard(updated);
      addToast(`Removed dependency: ${taskId} no longer depends on ${prereqId}`, 'success');
    } catch (err: any) {
      addToast(err.message || 'Failed to remove dependency', 'error');
    }
  };

  const handleAcceptAISuggestion = async (id: string) => {
    try {
      const updated = await api.acceptAISuggestion(id);
      setBoard(updated);
      addToast('Accepted AI dependency suggestion into graph', 'success');
    } catch (err: any) {
      addToast(err.message || 'Failed to accept suggestion', 'error');
    }
  };

  const handleRejectAISuggestion = async (id: string) => {
    try {
      await api.rejectAISuggestion(id);
      if (board) {
        setBoard({
          ...board,
          pending_suggestions: board.pending_suggestions.filter((s) => s.id !== id),
        });
      }
      addToast('Rejected AI suggestion', 'success');
    } catch (err: any) {
      addToast(err.message || 'Failed to reject suggestion', 'error');
    }
  };

  const handleGenerateAISuggestions = async () => {
    try {
      await api.generateAISuggestions();
      // Reload full board state to update suggestions
      const freshBoard = await api.getBoard();
      setBoard(freshBoard);
      addToast('Generated AI suggestions with DAG validation', 'success');
    } catch (err: any) {
      addToast(err.message || 'AI generation failed', 'error');
    }
  };

  const handleResetSeed = async () => {
    if (!confirm('Reset board to 10 benchmark seeded tasks? This will reset all edits.')) return;
    try {
      setLoading(true);
      const fresh = await api.resetSeed();
      setBoard(fresh);
      addToast('Board reset to 10 canonical benchmark tasks', 'success');
    } catch (err: any) {
      addToast(err.message || 'Failed to reset board', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Filtered Tasks
  const filteredTasks = useMemo(() => {
    if (!board) return [];
    return board.tasks.filter((task) => {
      // Search filter
      const matchesSearch =
        !searchQuery ||
        task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        task.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        task.description.toLowerCase().includes(searchQuery.toLowerCase());

      // Status filter
      const matchesStatus =
        filterStatus === 'all' ||
        (filterStatus === 'ready' && !task.is_blocked) ||
        (filterStatus === 'blocked' && task.is_blocked);

      return matchesSearch && matchesStatus;
    });
  }, [board, searchQuery, filterStatus]);

  const depsTargetTask = useMemo(() => {
    if (!board || !depsTargetTaskId) return null;
    return board.tasks.find((t) => t.id === depsTargetTaskId) || null;
  }, [board, depsTargetTaskId]);

  if (loading && !board) {
    return (
      <div
        style={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '14px',
          background: 'var(--bg-primary)',
          color: 'var(--text-main)',
        }}
      >
        <Loader2 size={36} className="spin-animation" style={{ color: 'var(--accent-primary)' }} />
        <p style={{ fontSize: '0.95rem', fontWeight: 600 }}>Loading TaskFlow Pro Engine...</p>
      </div>
    );
  }

  return (
    <div className="app-container">
      {board && (
        <Header
          stats={board.stats}
          criticalPathActive={criticalPathActive}
          onToggleCriticalPath={() => setCriticalPathActive(!criticalPathActive)}
          onOpenNewTask={() => {
            setEditingTask(null);
            setIsTaskModalOpen(true);
          }}
          onOpenAISuggestions={() => setIsAIDrawerOpen(true)}
          onOpenDAGVisualizer={() => setIsDAGModalOpen(true)}
          onResetSeed={handleResetSeed}
          pendingSuggestionsCount={board.pending_suggestions.length}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          filterStatus={filterStatus}
          onFilterStatusChange={setFilterStatus}
        />
      )}

      {board && (
        <KanbanBoard
          tasks={filteredTasks}
          criticalPathActive={criticalPathActive}
          onMoveTask={handleMoveTask}
          onEditTask={(t) => {
            setEditingTask(t);
            setIsTaskModalOpen(true);
          }}
          onManageDeps={(t) => {
            setDepsTargetTaskId(t.id);
            setIsDepsModalOpen(true);
          }}
          onDeleteTask={handleDeleteTask}
          onErrorToast={(msg) => addToast(msg, 'error')}
        />
      )}

      {/* Task Creation / Edit Modal */}
      {isTaskModalOpen && (
        <TaskModal
          task={editingTask}
          allTasks={board?.tasks || []}
          onClose={() => {
            setIsTaskModalOpen(false);
            setEditingTask(null);
          }}
          onSubmit={handleCreateOrUpdateTask}
        />
      )}

      {/* Dependency Graph Modal */}
      {isDepsModalOpen && depsTargetTask && (
        <DependencyModal
          task={depsTargetTask}
          allTasks={board?.tasks || []}
          onClose={() => {
            setIsDepsModalOpen(false);
            setDepsTargetTaskId(null);
          }}
          onAddDependency={handleAddDependency}
          onRemoveDependency={handleRemoveDependency}
        />
      )}

      {/* AI Suggestion Drawer */}
      <AISuggestionDrawer
        isOpen={isAIDrawerOpen}
        onClose={() => setIsAIDrawerOpen(false)}
        suggestions={board?.pending_suggestions || []}
        onAccept={handleAcceptAISuggestion}
        onReject={handleRejectAISuggestion}
        onRefreshSuggestions={handleGenerateAISuggestions}
      />

      {/* DAG Graph Visualizer */}
      {isDAGModalOpen && board && (
        <DAGVisualizerModal
          tasks={board.tasks}
          dependencies={board.dependencies}
          criticalPath={board.critical_path}
          onClose={() => setIsDAGModalOpen(false)}
          onSelectTask={(task) => {
            setDepsTargetTaskId(task.id);
            setIsDepsModalOpen(true);
          }}
        />
      )}

      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            {toast.type === 'error' ? (
              <AlertCircle size={18} style={{ color: '#fb7185', flexShrink: 0 }} />
            ) : (
              <CheckCircle size={18} style={{ color: '#34d399', flexShrink: 0 }} />
            )}
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default App;
