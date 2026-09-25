import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import type { Task, TaskColumn } from '../types';
import { TaskCard } from './TaskCard';

interface KanbanColumnProps {
  id: TaskColumn;
  title: string;
  tasks: Task[];
  criticalPathActive: boolean;
  onEditTask: (task: Task) => void;
  onManageDeps: (task: Task) => void;
  onDeleteTask: (id: string) => void;
}

export const KanbanColumn: React.FC<KanbanColumnProps> = ({
  id,
  title,
  tasks,
  criticalPathActive,
  onEditTask,
  onManageDeps,
  onDeleteTask,
}) => {
  const { setNodeRef, isOver } = useDroppable({
    id,
    data: { column: id },
  });

  return (
    <div
      ref={setNodeRef}
      className={`kanban-column column-${id}`}
      style={{
        borderColor: isOver ? 'var(--border-focus)' : undefined,
        background: isOver ? 'rgba(30, 41, 59, 0.7)' : undefined,
      }}
    >
      <div className="column-header">
        <div className="column-title-group">
          <div className="column-indicator" />
          <h2 className="column-title">{title}</h2>
        </div>
        <span className="column-count">{tasks.length}</span>
      </div>

      <div className="column-cards-list">
        <SortableContext
          items={tasks.map((t) => t.id)}
          strategy={verticalListSortingStrategy}
        >
          {tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              criticalPathActive={criticalPathActive}
              onEdit={onEditTask}
              onManageDeps={onManageDeps}
              onDelete={onDeleteTask}
            />
          ))}
        </SortableContext>

        {tasks.length === 0 && (
          <div className="column-empty-placeholder">
            <span>No tasks in {title}</span>
          </div>
        )}
      </div>
    </div>
  );
};
