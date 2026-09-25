import React, { useState } from 'react';
import {
  X,
  Plus,
  Trash2,
  ArrowRight,
  ShieldAlert,
  GitFork,
} from 'lucide-react';
import type { Task } from '../types';

interface DependencyModalProps {
  task: Task;
  allTasks: Task[];
  onClose: () => void;
  onAddDependency: (taskId: string, prereqId: string) => Promise<{ success: boolean; error?: string; loop?: string[] }>;
  onRemoveDependency: (taskId: string, prereqId: string) => void;
}

export const DependencyModal: React.FC<DependencyModalProps> = ({
  task,
  allTasks,
  onClose,
  onAddDependency,
  onRemoveDependency,
}) => {
  const [selectedPrereqId, setSelectedPrereqId] = useState('');
  const [cycleError, setCycleError] = useState<{ message: string; loop?: string[] } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Eligible tasks: cannot depend on itself, and cannot depend on existing prerequisites
  const eligiblePrereqs = allTasks.filter(
    (t) => t.id !== task.id && !task.prerequisites.includes(t.id)
  );

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPrereqId) return;

    setCycleError(null);
    setIsSubmitting(true);

    const res = await onAddDependency(task.id, selectedPrereqId);
    setIsSubmitting(false);

    if (res.success) {
      setSelectedPrereqId('');
    } else {
      setCycleError({
        message: res.error || 'Failed to add dependency',
        loop: res.loop,
      });
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <GitFork size={18} style={{ color: 'var(--accent-primary)' }} />
            <h3 className="modal-title">Dependency Graph Manager</h3>
          </div>
          <button className="card-icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {/* Target Task Summary */}
          <div
            style={{
              padding: '12px 14px',
              background: 'rgba(15, 23, 42, 0.6)',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', fontFamily: 'var(--font-mono)' }}>
              Managing Task: {task.id}
            </div>
            <div style={{ fontWeight: 600, fontSize: '1rem', marginTop: '2px' }}>
              {task.title}
            </div>
          </div>

          {/* Cycle Rejection Visualizer if triggered */}
          {cycleError && (
            <div className="cycle-error-box">
              <div className="cycle-error-title">
                <ShieldAlert size={18} />
                <span>Cycle Prevention Triggered — Graph Preserved</span>
              </div>
              <p style={{ fontSize: '0.82rem', lineHeight: 1.4 }}>
                {cycleError.message}
              </p>
              {cycleError.loop && cycleError.loop.length > 0 && (
                <div style={{ marginTop: '4px' }}>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    Detected illegal cyclic path:
                  </div>
                  <div className="cycle-loop-visual">
                    {cycleError.loop.map((nodeId, idx) => (
                      <React.Fragment key={idx}>
                        <span className="loop-node">{nodeId}</span>
                        {idx < (cycleError.loop?.length || 0) - 1 && (
                          <ArrowRight size={12} className="loop-arrow" />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Incoming Prerequisites Section */}
          <div>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px' }}>
              Prerequisites (Tasks this must wait for before starting)
            </h4>

            {task.prerequisites.length === 0 ? (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', fontStyle: 'italic' }}>
                No prerequisites. This task is immediately Ready to start.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {task.prerequisites.map((prereqId) => {
                  const prereqTask = allTasks.find((t) => t.id === prereqId);
                  const isDone = prereqTask?.column === 'done';

                  return (
                    <div
                      key={prereqId}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 12px',
                        background: 'rgba(30, 41, 59, 0.4)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '6px',
                      }}
                    >
                      <div>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-subtle)' }}>
                          {prereqId}
                        </span>
                        <div style={{ fontSize: '0.85rem', fontWeight: 500 }}>
                          {prereqTask?.title || prereqId}
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          className={`status-badge ${isDone ? 'badge-ready' : 'badge-blocked'}`}
                          style={{ fontSize: '0.68rem' }}
                        >
                          {isDone ? 'Completed' : 'Pending'}
                        </span>
                        <button
                          className="card-icon-btn"
                          title="Remove prerequisite"
                          onClick={() => onRemoveDependency(task.id, prereqId)}
                        >
                          <Trash2 size={14} style={{ color: '#fb7185' }} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Add Prerequisite Form */}
          <form onSubmit={handleAdd} style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
            <label className="form-label">Add New Prerequisite</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <select
                className="form-select"
                style={{ flex: 1 }}
                value={selectedPrereqId}
                onChange={(e) => setSelectedPrereqId(e.target.value)}
              >
                <option value="">-- Select Prerequisite Task --</option>
                {eligiblePrereqs.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.id}: {t.title} ({t.column})
                  </option>
                ))}
              </select>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={!selectedPrereqId || isSubmitting}
              >
                <Plus size={15} />
                <span>Add</span>
              </button>
            </div>
          </form>

          {/* Outgoing Dependents preview */}
          {task.dependents.length > 0 && (
            <div style={{ paddingTop: '10px', borderTop: '1px solid var(--border-subtle)' }}>
              <h4 style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginBottom: '6px' }}>
                Dependents (Downstream tasks waiting on this task):
              </h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {task.dependents.map((depId) => (
                  <span key={depId} className="dep-chip">
                    {depId}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
