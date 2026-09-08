'use client';

import { useState } from 'react';
import { useAIAvailability, useGenerateAchievements } from '@/hooks/useAI';
import type { ExperienceEntry } from '@/types/cv';

/**
 * Suggests achievement bullets for one role from its description.
 *
 * Suggestions are never written straight into the CV: each one is added only
 * when picked, so a generated line cannot quietly become part of the document.
 */
export function AchievementSuggestions({
  entry,
  onAdd,
}: {
  entry: ExperienceEntry;
  onAdd: (achievement: string) => void;
}) {
  const { ready } = useAIAvailability();
  const generate = useGenerateAchievements();
  const [open, setOpen] = useState(false);
  const [used, setUsed] = useState<Set<string>>(new Set());

  if (!ready) return null;

  const canGenerate = Boolean(entry.description?.trim() || entry.title.trim());

  const run = () => {
    setOpen(true);
    generate.mutate({
      description: entry.description || undefined,
      job_title: entry.title || undefined,
      company: entry.company || undefined,
      num_variations: 5,
    });
  };

  const suggestions = (generate.data ?? []).filter((text) => !used.has(text));

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={run}
        disabled={!canGenerate || generate.isPending}
        className="inline-flex items-center gap-1.5 h-7 px-2.5 self-start rounded-control
          text-meta text-accent-700 hover:bg-accent-500/10 transition-colors
          disabled:opacity-40 disabled:hover:bg-transparent"
        title={canGenerate ? undefined : 'Add a description or job title first'}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3l2.1 5.4L19.5 10l-5.4 2.1L12 17.5l-2.1-5.4L4.5 10l5.4-1.6z" />
        </svg>
        {generate.isPending ? 'Suggesting…' : 'Suggest achievements'}
      </button>

      {open && generate.isPending && (
        <p className="text-meta text-ink-subtle">
          Asking your provider — this can take a moment.
        </p>
      )}

      {open && !generate.isPending && generate.data && suggestions.length === 0 && (
        <p className="text-meta text-ink-subtle">
          {used.size > 0 ? 'All suggestions used.' : 'No suggestions came back.'}
        </p>
      )}

      {suggestions.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-panel border border-dashed border-accent-500/40 p-2.5">
          <div className="flex items-center gap-2">
            <span className="rail-label">Suggestions</span>
            <div className="flex-1" />
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-meta text-ink-muted hover:text-ink"
            >
              Dismiss
            </button>
          </div>
          {suggestions.map((text) => (
            <div key={text} className="flex items-start gap-2">
              <p className="flex-1 min-w-0 text-ui leading-relaxed">{text}</p>
              <button
                type="button"
                className="btn btn-sm btn-secondary flex-shrink-0"
                onClick={() => {
                  onAdd(text);
                  setUsed((current) => new Set(current).add(text));
                }}
              >
                Add
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
