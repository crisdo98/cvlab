'use client';

import { AddButton, Field, IconButton, TextArea, TextInput } from '@/components/ui/Field';
import type { EditorProps } from './types';
import type {
  CertificationEntry,
  EducationEntry,
  StructuredSectionContent,
} from '@/types/cv';

/** Shared card chrome for the entry-list editors. */
function EntryCard({
  index,
  summary,
  onRemove,
  children,
}: {
  index: number;
  summary: string;
  onRemove: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="card px-4 pt-3 pb-4">
      <div className="sticky -top-px z-10 flex items-center justify-between gap-2 mb-3.5 pt-1 pb-2.5 bg-surface border-b border-line-soft">
        <span className="font-mono text-micro font-medium uppercase tracking-[0.06em] text-ink-subtle">
          Entry {index + 1}
        </span>
        <span className="flex-1 truncate text-ui font-medium">
          {summary || <span className="text-ink-faint">Untitled</span>}
        </span>
        <IconButton label={`Remove entry ${index + 1}`} tone="danger" onClick={onRemove}>
          <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
          </svg>
        </IconButton>
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------ Education */

export function EducationEditor({ form }: EditorProps<StructuredSectionContent>) {
  const { content, update } = form;
  const entries = content.entries as EducationEntry[];

  const patch = (index: number, next: Partial<EducationEntry>) =>
    update((draft) => ({
      ...draft,
      entries: draft.entries.map((e, i) => (i === index ? { ...e, ...next } : e)),
    }));

  return (
    <div className="flex flex-col gap-3">
      {entries.map((entry, index) => (
        <EntryCard
          key={entry.id}
          index={index}
          summary={entry.degree}
          onRemove={() =>
            update((draft) => ({
              ...draft,
              entries: draft.entries.filter((_, i) => i !== index),
            }))
          }
        >
          <Field label="Degree" required>
            {(id) => (
              <TextInput
                id={id}
                value={entry.degree}
                placeholder="e.g. BSc Computer Science"
                onChange={(e) => patch(index, { degree: e.target.value })}
              />
            )}
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Institution" required>
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.institution}
                  onChange={(e) => patch(index, { institution: e.target.value })}
                />
              )}
            </Field>
            <Field label="Location">
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.location ?? ''}
                  onChange={(e) => patch(index, { location: e.target.value })}
                />
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="Start date">
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.start_date ?? ''}
                  onChange={(e) => patch(index, { start_date: e.target.value })}
                />
              )}
            </Field>
            <Field label="End date">
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.end_date ?? ''}
                  onChange={(e) => patch(index, { end_date: e.target.value })}
                />
              )}
            </Field>
            <Field label="Grade">
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.gpa ?? ''}
                  placeholder="e.g. First class"
                  onChange={(e) => patch(index, { gpa: e.target.value })}
                />
              )}
            </Field>
          </div>

          <Field label="Description">
            {(id) => (
              <TextArea
                id={id}
                rows={3}
                value={entry.description ?? ''}
                onChange={(e) => patch(index, { description: e.target.value })}
              />
            )}
          </Field>
        </EntryCard>
      ))}

      <AddButton
        className="h-9 w-full"
        onClick={() =>
          update((draft) => ({
            ...draft,
            entries: [
              ...draft.entries,
              {
                id: crypto.randomUUID(),
                degree: '',
                institution: '',
                location: '',
                start_date: '',
                end_date: '',
                gpa: '',
                description: '',
              } satisfies EducationEntry,
            ],
          }))
        }
      >
        Add qualification
      </AddButton>
    </div>
  );
}

/* ------------------------------------------------------- Certifications */

export function CertificationEditor({ form }: EditorProps<StructuredSectionContent>) {
  const { content, update } = form;
  const entries = content.entries as CertificationEntry[];

  const patch = (index: number, next: Partial<CertificationEntry>) =>
    update((draft) => ({
      ...draft,
      entries: draft.entries.map((e, i) => (i === index ? { ...e, ...next } : e)),
    }));

  return (
    <div className="flex flex-col gap-3">
      {entries.map((entry, index) => (
        <EntryCard
          key={entry.id}
          index={index}
          summary={entry.name}
          onRemove={() =>
            update((draft) => ({
              ...draft,
              entries: draft.entries.filter((_, i) => i !== index),
            }))
          }
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Name" required>
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.name}
                  placeholder="e.g. AWS Solutions Architect"
                  onChange={(e) => patch(index, { name: e.target.value })}
                />
              )}
            </Field>
            <Field label="Issuer" required>
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.issuer}
                  onChange={(e) => patch(index, { issuer: e.target.value })}
                />
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="Issued">
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.date ?? ''}
                  onChange={(e) => patch(index, { date: e.target.value })}
                />
              )}
            </Field>
            <Field label="Expires">
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.expiry_date ?? ''}
                  onChange={(e) => patch(index, { expiry_date: e.target.value })}
                />
              )}
            </Field>
            <Field label="Credential ID">
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.credential_id ?? ''}
                  onChange={(e) => patch(index, { credential_id: e.target.value })}
                />
              )}
            </Field>
          </div>
        </EntryCard>
      ))}

      <AddButton
        className="h-9 w-full"
        onClick={() =>
          update((draft) => ({
            ...draft,
            entries: [
              ...draft.entries,
              {
                id: crypto.randomUUID(),
                name: '',
                issuer: '',
                date: '',
                expiry_date: '',
                credential_id: '',
              } satisfies CertificationEntry,
            ],
          }))
        }
      >
        Add certification
      </AddButton>
    </div>
  );
}
