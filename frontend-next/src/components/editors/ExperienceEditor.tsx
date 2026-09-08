'use client';

import { useState } from 'react';
import {
  AddButton,
  AutoGrowTextArea,
  Checkbox,
  Field,
  IconButton,
  TextArea,
  TextInput,
} from '@/components/ui/Field';
import { AchievementSuggestions } from './AchievementSuggestions';
import type { EditorProps } from './types';
import type { ExperienceEntry, StructuredSectionContent } from '@/types/cv';

const blankEntry = (): ExperienceEntry => ({
  id: crypto.randomUUID(),
  title: '',
  company: '',
  location: '',
  start_date: '',
  end_date: '',
  current: false,
  description: '',
  achievements: [],
});

export function ExperienceEditor({ form }: EditorProps<StructuredSectionContent>) {
  const { content, update } = form;
  const entries = content.entries as ExperienceEntry[];

  // Bulk edit swaps one entry's achievement rows for a plain block of text.
  const [bulkOpen, setBulkOpen] = useState<Record<string, boolean>>({});
  const [bulkText, setBulkText] = useState<Record<string, string>>({});

  const patchEntry = (index: number, patch: Partial<ExperienceEntry>) =>
    update((draft) => ({
      ...draft,
      entries: draft.entries.map((entry, i) =>
        i === index ? { ...entry, ...patch } : entry
      ),
    }));

  const toggleBulk = (entry: ExperienceEntry) => {
    const opening = !bulkOpen[entry.id];
    if (opening) {
      setBulkText((t) => ({ ...t, [entry.id]: entry.achievements.join('\n') }));
    }
    setBulkOpen((o) => ({ ...o, [entry.id]: opening }));
  };

  const onBulkInput = (index: number, entry: ExperienceEntry, text: string) => {
    setBulkText((t) => ({ ...t, [entry.id]: text }));
    // Keep the structured list in step as it is typed, so the preview updates
    // and nothing is lost when bulk mode closes.
    patchEntry(index, {
      achievements: text
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean),
    });
  };

  return (
    <div className="flex flex-col gap-3">
      {entries.length === 0 && (
        <p className="text-ui text-ink-muted py-4">
          No roles yet. Add your first one below.
        </p>
      )}

      {entries.map((entry, index) => (
        <div key={entry.id} className="card px-4 pt-3 pb-4">
          {/* Sticky so it stays visible while a long role is scrolled. */}
          <div className="sticky -top-px z-10 flex items-center justify-between gap-2 mb-3.5 pt-1 pb-2.5 bg-surface border-b border-line-soft">
            <span className="font-mono text-micro font-medium uppercase tracking-[0.06em] text-ink-subtle">
              Entry {index + 1}
            </span>
            <span className="flex-1 truncate text-ui font-medium">
              {entry.title || <span className="text-ink-faint">Untitled role</span>}
            </span>
            <IconButton
              label={`Remove entry ${index + 1}`}
              tone="danger"
              onClick={() =>
                update((draft) => ({
                  ...draft,
                  entries: draft.entries.filter((_, i) => i !== index),
                }))
              }
            >
              <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
              </svg>
            </IconButton>
          </div>

          <div className="flex flex-col gap-3">
            <Field label="Job title" required>
              {(id) => (
                <TextInput
                  id={id}
                  value={entry.title}
                  placeholder="e.g. Head of Data Engineering"
                  onChange={(e) => patchEntry(index, { title: e.target.value })}
                />
              )}
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Company">
                {(id) => (
                  <TextInput
                    id={id}
                    value={entry.company ?? ''}
                    onChange={(e) => patchEntry(index, { company: e.target.value })}
                  />
                )}
              </Field>
              <Field label="Location">
                {(id) => (
                  <TextInput
                    id={id}
                    value={entry.location ?? ''}
                    onChange={(e) => patchEntry(index, { location: e.target.value })}
                  />
                )}
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:items-end">
              <Field label="Start date">
                {(id) => (
                  <TextInput
                    id={id}
                    value={entry.start_date ?? ''}
                    placeholder="March 2023"
                    onChange={(e) => patchEntry(index, { start_date: e.target.value })}
                  />
                )}
              </Field>
              <Field label="End date">
                {(id) => (
                  <TextInput
                    id={id}
                    value={entry.current ? '' : (entry.end_date ?? '')}
                    placeholder={entry.current ? 'Present' : 'e.g. Dec 2022'}
                    disabled={entry.current}
                    onChange={(e) => patchEntry(index, { end_date: e.target.value })}
                  />
                )}
              </Field>
              <div className="h-8 flex items-center">
                <Checkbox
                  label="Currently working here"
                  checked={Boolean(entry.current)}
                  onChange={(e) => patchEntry(index, { current: e.target.checked })}
                />
              </div>
            </div>

            <Field label="Description">
              {(id) => (
                <TextArea
                  id={id}
                  rows={3}
                  value={entry.description ?? ''}
                  onChange={(e) => patchEntry(index, { description: e.target.value })}
                />
              )}
            </Field>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <span className="text-meta font-medium text-ink-muted">Achievements</span>
                <span className="font-mono text-micro text-ink-faint">
                  {entry.achievements.length}
                </span>
                <div className="flex-1" />
                <button
                  type="button"
                  onClick={() => toggleBulk(entry)}
                  className={`h-6 px-2 rounded-[3px] text-meta transition-colors ${
                    bulkOpen[entry.id]
                      ? 'text-accent-700 bg-accent-500/10'
                      : 'text-ink-muted hover:bg-line-soft hover:text-ink'
                  }`}
                >
                  {bulkOpen[entry.id] ? 'Done' : 'Bulk edit'}
                </button>
              </div>

              {bulkOpen[entry.id] ? (
                <>
                  <TextArea
                    rows={10}
                    value={bulkText[entry.id] ?? ''}
                    placeholder="One achievement per line"
                    onChange={(e) => onBulkInput(index, entry, e.target.value)}
                  />
                  <p className="text-meta text-ink-subtle">
                    One per line. Blank lines are ignored.
                  </p>
                </>
              ) : (
                <>
                  <div className="flex flex-col gap-1.5">
                    {entry.achievements.map((achievement, achIndex) => (
                      <div key={achIndex} className="flex items-start gap-2">
                        <AutoGrowTextArea
                          value={achievement}
                          placeholder="Key achievement or accomplishment"
                          onChange={(e) =>
                            patchEntry(index, {
                              achievements: entry.achievements.map((a, i) =>
                                i === achIndex ? e.target.value : a
                              ),
                            })
                          }
                        />
                        <IconButton
                          label="Remove achievement"
                          tone="danger"
                          className="mt-1"
                          onClick={() =>
                            patchEntry(index, {
                              achievements: entry.achievements.filter((_, i) => i !== achIndex),
                            })
                          }
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M18 6L6 18M6 6l12 12" />
                          </svg>
                        </IconButton>
                      </div>
                    ))}
                  </div>
                  <AddButton
                    onClick={() =>
                      patchEntry(index, { achievements: [...entry.achievements, ''] })
                    }
                  >
                    Add achievement
                  </AddButton>

                  <AchievementSuggestions
                    entry={entry}
                    onAdd={(achievement) =>
                      patchEntry(index, {
                        achievements: [...entry.achievements, achievement],
                      })
                    }
                  />
                </>
              )}
            </div>
          </div>
        </div>
      ))}

      <AddButton
        className="h-9 w-full"
        onClick={() =>
          update((draft) => ({ ...draft, entries: [...draft.entries, blankEntry()] }))
        }
      >
        Add role
      </AddButton>
    </div>
  );
}
