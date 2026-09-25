import React, { useState } from 'react';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core';
import type { Task, TaskColumn } from '../types';
import { KanbanColumn } from './KanbanColumn';
import { TaskCard } from './TaskCard';

interface KanbanBoardProps {
  tasks: Task[];
  criticalPathActive: boolean;
  onMoveTask: (taskId: string, targetColumn: TaskColumn, newPosition?: number) => void;
  onEditTask: (task: Task) => void;
  onManageDeps: (task: Task) => void;
  onDeleteTask: (id: string) => void;
  onErrorToast: (msg: string) => void;
}

const COLUMNS: { id: TaskColumn; title: string }[] = [
  { id: 'backlog', title: 'Backlog' },
  { id: 'in_progress', title: 'In Progress' },
  { id: 'review', title: 'Review' },
  { id: 'done', title: 'Done' },
];

export const KanbanBoard: React.FC<KanbanBoardProps> = ({
  tasks,
  criticalPathActive,
  onMoveTask,
  onEditTask,
  onManageDeps,
  onDeleteTask,
  onErrorToast,
}) => {
  const [activeTask, setActiveTask] = useState<Task | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5, // 5px drag threshold to avoid accidental drags when clicking buttons
      },
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    const task = tasks.find((t) => t.id === event.active.id);
    if (task) {
      setActiveTask(task);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveTask(null);

    if (!over) return;

    const activeId = active.id as string;
    const task = tasks.find((t) => t.id === activeId);
    if (!task) return;

    // Check if dropped onto a column or another card
    let targetColumn: TaskColumn | null = null;

    if (COLUMNS.some((c) => c.id === over.id)) {
      targetColumn = over.id as TaskColumn;
    } else {
      // Dropped onto another task
      const overTask = tasks.find((t) => t.id === over.id);
      if (overTask) {
        targetColumn = overTask.column;
      }
    }

    if (!targetColumn) return;

    // Prevent moving Blocked tasks forward
    if (task.is_blocked && (targetColumn === 'in_progress' || targetColumn === 'review' || targetColumn === 'done')) {
      onErrorToast(
        `Action Blocked: Task "${task.title}" cannot be moved to ${targetColumn.replace('_', ' ').toUpperCase()} ` +
        `because prerequisite(s) [${task.blocking_task_ids.join(', ')}] are not completed.`
      );
      return;
    }

    if (task.column !== targetColumn) {
      onMoveTask(activeId, targetColumn);
    }
  };

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <main className="board-wrapper">
        {COLUMNS.map((col) => {
          const colTasks = tasks
            .filter((t) => t.column === col.id)
            .sort((a, b) => a.position - b.position);

          return (
            <KanbanColumn
              key={col.id}
              id={col.id}
              title={col.title}
              tasks={colTasks}
              criticalPathActive={criticalPathActive}
              onEditTask={onEditTask}
              onManageDeps={onManageDeps}
              onDeleteTask={onDeleteTask}
            />
          );
        })}
      </main>

      <DragOverlay>
        {activeTask ? (
          <div style={{ transform: 'rotate(2deg)', width: '320px' }}>
            <TaskCard
              task={activeTask}
              criticalPathActive={criticalPathActive}
              onEdit={() => {}}
              onManageDeps={() => {}}
              onDelete={() => {}}
            />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
};
