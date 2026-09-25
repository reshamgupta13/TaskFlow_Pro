import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  CheckCircle2,
  Lock,
  Flame,
  AlertTriangle,
  Calendar,
  Clock,
  GitFork,
  Edit2,
  Trash2,
} from 'lucide-react';
import type { Task } from '../types';

interface TaskCardProps {
  task: Task;
  criticalPathActive: boolean;
  onEdit: (task: Task) => void;
  onManageDeps: (task: Task) => void;
  onDelete: (id: string) => void;
}

export const TaskCard: React.FC<TaskCardProps> = ({
  task,
  criticalPathActive,
  onEdit,
  onManageDeps,
  onDelete,
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id, data: { task } });

  const style = {
    transform: CSS.Translate.toString(transform),
    transition,
  };

  const isHighlightedCritical = criticalPathActive && task.is_critical_path;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`task-card ${isDragging ? 'is-dragging' : ''} ${
        task.is_critical_path ? 'is-critical' : ''
      } ${isHighlightedCritical ? 'critical-highlight' : ''}`}
      {...attributes}
      {...listeners}
    >
      <div className="card-header">
        <span className="card-id-tag">{task.id}</span>
        <div className="card-badges">
          {task.is_blocked ? (
            <span
              className="status-badge badge-blocked"
              title={`Blocked by unmet prerequisite(s): ${task.blocking_task_ids.join(', ')}`}
            >
              <Lock size={11} />
              Blocked
            </span>
          ) : (
            <span className="status-badge badge-ready">
              <CheckCircle2 size={11} />
              Ready
            </span>
          )}

          {task.is_critical_path && (
            <span className="status-badge badge-critical" title="Longest duration path driving completion">
              <Flame size={11} />
              Critical
            </span>
          )}
        </div>
      </div>

      <div className="card-title">{task.title}</div>

      {task.description && <p className="card-desc">{task.description}</p>}

      {/* Regression Warning banner if task in progress while prerequisite regressed */}
      {task.has_regression_warning && (
        <div className="card-warning-banner">
          <AlertTriangle size={14} style={{ flexShrink: 0 }} />
          <span>{task.warning_message || 'Downstream task in flight while prerequisite is not Done!'}</span>
        </div>
      )}

      {/* Schedule & Duration Timeline */}
      <div className="card-timeline">
        <div className="timeline-dates">
          <Calendar size={12} />
          <span>{task.start_date || task.planned_start}</span>
          <span>→</span>
          <span>{task.end_date || '...'}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
          <Clock size={12} />
          <span>{task.duration_days}d</span>
        </div>
      </div>

      {/* Dependencies preview */}
      {task.prerequisites.length > 0 && (
        <div className="card-deps-section">
          <div className="deps-label">
            <GitFork size={11} />
            <span>Prerequisites:</span>
          </div>
          <div className="deps-chips">
            {task.prerequisites.map((pId) => {
              const isBlocking = task.blocking_task_ids.includes(pId);
              return (
                <span
                  key={pId}
                  className={`dep-chip ${isBlocking ? 'is-blocking' : ''}`}
                  title={isBlocking ? `Blocking: ${pId} is not Done` : `Satisfied: ${pId} is Done`}
                >
                  {pId}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Actions */}
      <div
        className="card-actions"
        onPointerDown={(e) => e.stopPropagation()} // Prevent drag when clicking buttons
      >
        <button
          className="card-icon-btn"
          title="Manage Dependencies & Cycles"
          onClick={() => onManageDeps(task)}
        >
          <GitFork size={14} />
        </button>

        <button
          className="card-icon-btn"
          title="Edit Task Details"
          onClick={() => onEdit(task)}
        >
          <Edit2 size={14} />
        </button>

        <button
          className="card-icon-btn"
          title="Delete Task"
          onClick={() => {
            if (confirm(`Delete task "${task.title}"? Dependencies will be safely cascaded.`)) {
              onDelete(task.id);
            }
          }}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
};
