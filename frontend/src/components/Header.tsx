import React from 'react';
import {
  GitBranch,
  Sparkles,
  RotateCcw,
  Plus,
  Flame,
  Network,
  CheckCircle2,
  Lock,
  Clock,
  Search,
} from 'lucide-react';
import type { BoardStats } from '../types';

interface HeaderProps {
  stats: BoardStats;
  criticalPathActive: boolean;
  onToggleCriticalPath: () => void;
  onOpenNewTask: () => void;
  onOpenAISuggestions: () => void;
  onOpenDAGVisualizer: () => void;
  onResetSeed: () => void;
  pendingSuggestionsCount: number;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  filterStatus: 'all' | 'ready' | 'blocked';
  onFilterStatusChange: (status: 'all' | 'ready' | 'blocked') => void;
}

export const Header: React.FC<HeaderProps> = ({
  stats,
  criticalPathActive,
  onToggleCriticalPath,
  onOpenNewTask,
  onOpenAISuggestions,
  onOpenDAGVisualizer,
  onResetSeed,
  pendingSuggestionsCount,
  searchQuery,
  onSearchChange,
  filterStatus,
  onFilterStatusChange,
}) => {
  return (
    <header className="app-header">
      <div className="header-top">
        <div className="brand">
          <div className="brand-icon">
            <GitBranch size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 className="brand-title">TaskFlow Pro</h1>
              <span className="brand-tag">DAG Engine v1.0</span>
            </div>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-subtle)' }}>
              Deterministic DAG Workflow & No-Compounding Scheduling
            </p>
          </div>
        </div>

        <div className="header-actions">
          <button
            className={`btn ${criticalPathActive ? 'btn-toggle-active' : ''}`}
            onClick={onToggleCriticalPath}
            title="Highlight longest duration chain via DP"
          >
            <Flame size={15} />
            <span>Critical Path ({stats.critical_path_length})</span>
          </button>

          <button className="btn" onClick={onOpenDAGVisualizer} title="View interactive DAG Graph">
            <Network size={15} />
            <span>DAG View</span>
          </button>

          <button className="btn btn-ai" onClick={onOpenAISuggestions}>
            <Sparkles size={15} />
            <span>AI Copilot</span>
            {pendingSuggestionsCount > 0 && (
              <span className="badge-count">{pendingSuggestionsCount}</span>
            )}
          </button>

          <button className="btn" onClick={onResetSeed} title="Reload 10 seeded benchmark tasks">
            <RotateCcw size={15} />
            <span>Reset Demo</span>
          </button>

          <button className="btn btn-primary" onClick={onOpenNewTask}>
            <Plus size={16} />
            <span>New Task</span>
          </button>
        </div>
      </div>

      <div className="header-bar">
        <div className="stats-group">
          <div className="stat-pill">
            <Clock size={14} />
            <span>Project Duration:</span>
            <span className="stat-num">{stats.total_duration_days} days</span>
          </div>

          <div className="stat-pill">
            <span>Total:</span>
            <span className="stat-num">{stats.total_tasks}</span>
          </div>

          <div
            className="stat-pill"
            style={{ cursor: 'pointer', borderColor: filterStatus === 'ready' ? 'var(--ready-border)' : undefined }}
            onClick={() => onFilterStatusChange(filterStatus === 'ready' ? 'all' : 'ready')}
          >
            <CheckCircle2 size={14} className="stat-ready" />
            <span className="stat-ready">Ready:</span>
            <span className="stat-num stat-ready">{stats.ready_tasks}</span>
          </div>

          <div
            className="stat-pill"
            style={{ cursor: 'pointer', borderColor: filterStatus === 'blocked' ? 'var(--blocked-border)' : undefined }}
            onClick={() => onFilterStatusChange(filterStatus === 'blocked' ? 'all' : 'blocked')}
          >
            <Lock size={14} className="stat-blocked" />
            <span className="stat-blocked">Blocked:</span>
            <span className="stat-num stat-blocked">{stats.blocked_tasks}</span>
          </div>

          <div className="stat-pill">
            <span>In Flight:</span>
            <span className="stat-num">{stats.in_progress_tasks}</span>
          </div>

          <div className="stat-pill">
            <span>Completed:</span>
            <span className="stat-num">{stats.done_tasks}</span>
          </div>
        </div>

        <div className="filter-controls">
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', color: 'var(--text-subtle)' }} />
            <input
              type="text"
              placeholder="Search tasks..."
              className="search-input"
              style={{ paddingLeft: '30px' }}
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
            />
          </div>
        </div>
      </div>
    </header>
  );
};
