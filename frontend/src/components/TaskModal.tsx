import React, { useState } from 'react';
import { X, Check } from 'lucide-react';
import type { Task, TaskColumn } from '../types';

interface TaskModalProps {
  task: Task | null; // null if creating
  allTasks: Task[];
  onClose: () => void;
  onSubmit: (data: {
    title: string;
    description: string;
    duration_days: number;
    planned_start: string;
    column?: TaskColumn;
    prerequisite_ids?: string[];
  }) => Promise<void>;
}

export const TaskModal: React.FC<TaskModalProps> = ({
  task,
  allTasks,
  onClose,
  onSubmit,
}) => {
  const isEditing = !!task;

  const [title, setTitle] = useState(task?.title || '');
  const [description, setDescription] = useState(task?.description || '');
  const [durationDays, setDurationDays] = useState(task?.duration_days || 2);
  const [plannedStart, setPlannedStart] = useState(
    task?.planned_start || new Date().toISOString().split('T')[0]
  );
  const [column, setColumn] = useState<TaskColumn>(task?.column || 'backlog');
  const [selectedPrereqs, setSelectedPrereqs] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsSubmitting(true);
    try {
      await onSubmit({
        title,
        description,
        duration_days: Number(durationDays),
        planned_start: plannedStart,
        column: !isEditing ? column : undefined,
        prerequisite_ids: !isEditing ? selectedPrereqs : undefined,
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  const togglePrereq = (id: string) => {
    setSelectedPrereqs((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isEditing ? `Edit Task: ${task.id}` : 'Create New Task'}
          </h3>
          <button className="card-icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label className="form-label">Task Title *</label>
              <input
                type="text"
                className="form-input"
                required
                placeholder="e.g. Implement OAuth Flow"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="Describe scope and acceptance criteria..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div className="form-group">
                <label className="form-label">Duration (Days) *</label>
                <input
                  type="number"
                  min={1}
                  max={365}
                  className="form-input"
                  required
                  value={durationDays}
                  onChange={(e) => setDurationDays(Number(e.target.value))}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Planned Start Date *</label>
                <input
                  type="date"
                  className="form-input"
                  required
                  value={plannedStart}
                  onChange={(e) => setPlannedStart(e.target.value)}
                />
              </div>
            </div>

            {!isEditing && (
              <>
                <div className="form-group">
                  <label className="form-label">Initial Column</label>
                  <select
                    className="form-select"
                    value={column}
                    onChange={(e) => setColumn(e.target.value as TaskColumn)}
                  >
                    <option value="backlog">Backlog</option>
                    <option value="in_progress">In Progress</option>
                    <option value="review">Review</option>
                    <option value="done">Done</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Initial Prerequisites (Optional)</label>
                  <div
                    style={{
                      maxHeight: '120px',
                      overflowY: 'auto',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '8px',
                      padding: '8px',
                      background: 'rgba(15, 23, 42, 0.4)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    {allTasks.map((t) => (
                      <label
                        key={t.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          fontSize: '0.8rem',
                          cursor: 'pointer',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedPrereqs.includes(t.id)}
                          onChange={() => togglePrereq(t.id)}
                        />
                        <span>
                          <strong>{t.id}</strong>: {t.title}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              <Check size={16} />
              <span>{isEditing ? 'Save Changes' : 'Create Task'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
