'use client';

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { useState } from 'react';
import { formatRelative } from '@/lib/cv-utils';
import { Stage, type Application } from '@/types/applicationTracker';

export const STAGES: { id: Stage; label: string }[] = [
  { id: Stage.WISHLIST, label: 'Wishlist' },
  { id: Stage.APPLIED, label: 'Applied' },
  { id: Stage.INTERVIEW, label: 'Interview' },
  { id: Stage.OFFER, label: 'Offer' },
  { id: Stage.REJECTED, label: 'Rejected' },
];

/** A muted accent per column, so the board reads at a glance without shouting. */
const STAGE_TONE: Record<Stage, string> = {
  [Stage.WISHLIST]: 'bg-ink-ghost',
  [Stage.APPLIED]: 'bg-primary-500',
  [Stage.INTERVIEW]: 'bg-accent-500',
  [Stage.OFFER]: 'bg-success-600',
  [Stage.REJECTED]: 'bg-danger-500',
};

function Card({
  application,
  onOpen,
  dragging = false,
}: {
  application: Application;
  onOpen?: (application: Application) => void;
  dragging?: boolean;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: application.id,
  });

  return (
    <div
      ref={setNodeRef}
      className={`card p-2.5 flex flex-col gap-1 ${
        isDragging ? 'opacity-30' : ''
      } ${dragging ? 'shadow-lg rotate-1' : ''}`}
    >
      <div className="flex items-start gap-1.5">
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="mt-0.5 flex-shrink-0 cursor-grab active:cursor-grabbing text-ink-ghost hover:text-ink-subtle"
          aria-label={`Move ${application.position_title}. Press space, then arrow keys.`}
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 9h16M4 15h16" />
          </svg>
        </button>
        <button
          type="button"
          onClick={() => onOpen?.(application)}
          className="flex-1 min-w-0 text-left"
        >
          <span className="block text-ui font-medium truncate">
            {application.position_title}
          </span>
          <span className="block text-meta text-ink-muted truncate">
            {application.company_name}
          </span>
        </button>
      </div>

      <div className="flex items-center gap-2 pl-[18px]">
        <span className="font-mono text-micro text-ink-faint">
          {formatRelative(application.application_date)}
        </span>
        {application.interviews?.length > 0 && (
          <span className="font-mono text-micro text-accent-700">
            {application.interviews.length} interview
            {application.interviews.length === 1 ? '' : 's'}
          </span>
        )}
      </div>
    </div>
  );
}

function Column({
  stage,
  label,
  applications,
  onOpen,
}: {
  stage: Stage;
  label: string;
  applications: Application[];
  onOpen: (application: Application) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });

  return (
    <div className="flex flex-col min-w-0 w-72 flex-shrink-0">
      <div className="flex items-center gap-2 h-9 px-1">
        <span className={`w-1.5 h-1.5 rounded-full ${STAGE_TONE[stage]}`} />
        <span className="rail-label">{label}</span>
        <span className="font-mono text-micro text-ink-faint">{applications.length}</span>
      </div>

      <div
        ref={setNodeRef}
        className={`flex-1 min-h-32 flex flex-col gap-2 p-2 rounded-panel border transition-colors ${
          isOver ? 'border-accent-500 bg-accent-500/5' : 'border-line bg-ground-panel'
        }`}
      >
        {applications.map((application) => (
          <Card key={application.id} application={application} onOpen={onOpen} />
        ))}
        {applications.length === 0 && (
          <p className="text-meta text-ink-faint px-1 py-2">Nothing here.</p>
        )}
      </div>
    </div>
  );
}

export function KanbanBoard({
  applications,
  onMove,
  onOpen,
}: {
  applications: Application[];
  onMove: (id: string, stage: Stage) => void;
  onOpen: (application: Application) => void;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);
  // KeyboardSensor matters here: without it the board is mouse-only, and a
  // card could not be moved between stages at all from the keyboard.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor)
  );

  const active = applications.find((a) => a.id === activeId) ?? null;

  const handleDragEnd = ({ active: dragged, over }: DragEndEvent) => {
    setActiveId(null);
    if (!over) return;
    const stage = over.id as Stage;
    const application = applications.find((a) => a.id === dragged.id);
    if (!application || application.stage === stage) return;
    onMove(application.id, stage);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={({ active: dragged }: DragStartEvent) => setActiveId(dragged.id as string)}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setActiveId(null)}
    >
      <div className="flex gap-3 overflow-x-auto pb-2">
        {STAGES.map(({ id, label }) => (
          <Column
            key={id}
            stage={id}
            label={label}
            applications={applications.filter((a) => a.stage === id)}
            onOpen={onOpen}
          />
        ))}
      </div>

      <DragOverlay>
        {active ? <Card application={active} dragging /> : null}
      </DragOverlay>
    </DndContext>
  );
}
