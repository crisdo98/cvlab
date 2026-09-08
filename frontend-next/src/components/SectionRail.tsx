'use client';

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { restrictToVerticalAxis } from '@dnd-kit/modifiers';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useEffect, useState } from 'react';
import { useRemoveSection, useReorderSections, useToggleSectionVisibility } from '@/hooks/useSections';
import type { Section } from '@/types/cv';

const CORE_TYPE = 'personal_info';

function entryCount(section: Section): number | null {
  const content = section.content as { entries?: unknown[]; items?: unknown[] };
  if (Array.isArray(content.entries)) return content.entries.length;
  if (Array.isArray(content.items)) return content.items.length;
  return null;
}

function SectionRow({
  section,
  selected,
  onSelect,
  onToggleVisible,
  onRemove,
}: {
  section: Section;
  selected: boolean;
  onSelect: () => void;
  onToggleVisible: () => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: section.id });

  const visible = section.visible !== false;
  const count = entryCount(section);

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-2.5 h-8 rounded-control border transition-colors ${
        isDragging ? 'opacity-40' : ''
      } ${
        selected
          ? 'pl-[7px] pr-2 bg-surface border-line border-l-2 border-l-accent-500'
          : 'px-2.5 border-transparent hover:bg-line-soft'
      }`}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="flex-shrink-0 cursor-grab active:cursor-grabbing text-ink-ghost hover:text-ink-subtle"
        aria-label={`Reorder ${section.title}`}
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 9h16M4 15h16" />
        </svg>
      </button>

      <button
        type="button"
        onClick={onSelect}
        className={`flex-1 min-w-0 text-left text-ui truncate ${
          selected ? 'font-semibold' : ''
        } ${visible ? '' : 'text-ink-faint'}`}
      >
        {section.title}
      </button>

      {count !== null && (
        <span className="font-mono text-micro text-ink-subtle">{count}</span>
      )}

      <button
        type="button"
        onClick={onToggleVisible}
        className="flex-shrink-0 text-ink-faint hover:text-ink-muted transition-colors"
        aria-label={visible ? `Hide ${section.title}` : `Show ${section.title}`}
        title={visible ? 'Visible in exports' : 'Hidden from exports'}
      >
        {visible ? (
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z" />
            <circle cx="12" cy="12" r="2.6" />
          </svg>
        ) : (
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 3l18 18M10.6 6.2A9.9 9.9 0 0112 6c6.4 0 10 6 10 6a17 17 0 01-3 3.8M6.2 7.4A17 17 0 002 12s3.6 6 10 6a9.7 9.7 0 004.4-1" />
          </svg>
        )}
      </button>

      {section.type !== CORE_TYPE && (
        <button
          type="button"
          onClick={onRemove}
          className="flex-shrink-0 text-ink-faint hover:text-danger-600 transition-colors"
          aria-label={`Remove ${section.title}`}
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
          </svg>
        </button>
      )}
    </div>
  );
}

export function SectionRail({
  cvId,
  sections,
  selectedId,
  onSelect,
}: {
  cvId: string;
  sections: Section[];
  selectedId: string | null;
  onSelect: (section: Section) => void;
}) {
  // Local order so the drag settles instantly, with the server call behind it.
  const [order, setOrder] = useState(sections);
  useEffect(() => setOrder(sections), [sections]);

  const reorder = useReorderSections(cvId);
  const toggleVisible = useToggleSectionVisibility(cvId);
  const remove = useRemoveSection(cvId);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    const from = order.findIndex((s) => s.id === active.id);
    const to = order.findIndex((s) => s.id === over.id);
    if (from < 0 || to < 0) return;

    const next = [...order];
    next.splice(to, 0, next.splice(from, 1)[0]);
    setOrder(next);
    reorder.mutate(next.map((s) => s.id));
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={[restrictToVerticalAxis]}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={order.map((s) => s.id)} strategy={verticalListSortingStrategy}>
        <div className="flex flex-col gap-px">
          {order.map((section) => (
            <div key={section.id}>
              <SectionRow
                section={section}
                selected={section.id === selectedId}
                onSelect={() => onSelect(section)}
                onToggleVisible={() =>
                  toggleVisible.mutate({
                    sectionId: section.id,
                    visible: section.visible === false,
                  })
                }
                onRemove={() => setConfirmingId(section.id)}
              />
              {confirmingId === section.id && (
                <div className="flex items-center gap-1.5 px-2.5 py-1.5">
                  <span className="text-meta text-ink-muted flex-1">Remove section?</span>
                  <button
                    type="button"
                    className="btn btn-sm btn-secondary"
                    onClick={() => setConfirmingId(null)}
                  >
                    No
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    onClick={() => {
                      remove.mutate(section.id);
                      setConfirmingId(null);
                    }}
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
