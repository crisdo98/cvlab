'use client';

import { useMemo, useState } from 'react';
import { useAddSections } from '@/hooks/useSections';
import { defaultSectionTitle, validateCustomSectionTitle, MAX_CUSTOM_TITLE } from '@/lib/sections';
import { SectionType, type Section } from '@/types/cv';

/** Everything that can be added, in the order the Vue picker offered them. */
const ADDABLE: SectionType[] = [
  SectionType.SUMMARY,
  SectionType.EXPERIENCE,
  SectionType.EDUCATION,
  SectionType.SKILLS,
  SectionType.LANGUAGES,
  SectionType.SOFTWARE,
  SectionType.CERTIFICATIONS,
  SectionType.ACCOMPLISHMENTS,
  SectionType.AFFILIATIONS,
  SectionType.INTERESTS,
  SectionType.WEBSITES,
];

const KIND: Partial<Record<SectionType, string>> = {
  [SectionType.SUMMARY]: 'Text',
  [SectionType.EXPERIENCE]: 'Entries',
  [SectionType.EDUCATION]: 'Entries',
  [SectionType.CERTIFICATIONS]: 'Entries',
};

export function AddSectionDialog({
  cvId,
  existing,
  onClose,
}: {
  cvId: string;
  existing: Section[];
  onClose: () => void;
}) {
  const add = useAddSections(cvId);
  const [picked, setPicked] = useState<SectionType[]>([]);
  const [customTitle, setCustomTitle] = useState('');
  const [filter, setFilter] = useState('');

  const present = useMemo(
    () => new Set(existing.map((section) => section.type)),
    [existing]
  );

  const visible = ADDABLE.filter((type) =>
    defaultSectionTitle(type).toLowerCase().includes(filter.trim().toLowerCase())
  );

  const customErrors = customTitle.trim() ? validateCustomSectionTitle(customTitle) : [];
  const total = picked.length + (customTitle.trim() && customErrors.length === 0 ? 1 : 0);

  const submit = async () => {
    await add.mutateAsync({
      types: picked,
      customTitle: customErrors.length === 0 ? customTitle : undefined,
    });
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 overflow-y-auto"
      style={{ background: 'rgb(22 32 43 / 0.34)' }}
      role="dialog"
      aria-modal="true"
      aria-label="Add sections"
    >
      <div className="w-full max-w-xl my-8 card rounded-dialog shadow-2xl">
        <div className="flex items-center gap-2.5 h-12 pl-[18px] pr-3 border-b border-line-soft">
          <h2 className="text-[15px] font-semibold tracking-[-0.01em]">Add sections</h2>
          <div className="flex-1" />
          {total > 0 && <span className="meta-mono">{total} selected</span>}
          <button
            type="button"
            onClick={onClose}
            className="w-[26px] h-[26px] flex items-center justify-center rounded-control text-ink-muted hover:bg-line-soft hover:text-ink"
            aria-label="Close"
          >
            <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex flex-col gap-[18px] p-[18px]">
          <div className="h-8 flex items-center gap-2 px-2.5 rounded-control border border-line-strong">
            <svg className="w-3.5 h-3.5 text-ink-subtle flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3.5-3.5" />
            </svg>
            <input
              className="flex-1 min-w-0 bg-transparent text-ui outline-none placeholder:text-ink-faint"
              placeholder="Filter section types"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-2">
            <span className="rail-label">Predefined</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {visible.map((type) => {
                const already = present.has(type);
                const checked = picked.includes(type);
                const label = defaultSectionTitle(type);

                return (
                  <label
                    key={type}
                    className={`flex items-center gap-2.5 h-9 px-2.5 rounded-control border text-ui transition-colors ${
                      already
                        ? 'cursor-not-allowed border-line-soft bg-ground-panel text-ink-faint'
                        : checked
                          ? 'cursor-pointer border-accent-500 bg-accent-500/[0.06] font-medium'
                          : 'cursor-pointer border-line-strong hover:border-ink-faint'
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="w-[15px] h-[15px] flex-shrink-0 rounded-[3px] border-ink-ghost text-accent-500 focus:ring-2 focus:ring-accent-500/30 disabled:cursor-not-allowed"
                      disabled={already}
                      checked={checked}
                      onChange={(e) =>
                        setPicked((current) =>
                          e.target.checked
                            ? [...current, type]
                            : current.filter((t) => t !== type)
                        )
                      }
                    />
                    <span className="flex-1 min-w-0 truncate">{label}</span>
                    <span className="font-mono text-[9.5px] uppercase tracking-[0.05em] text-ink-faint flex-shrink-0">
                      {already ? 'In CV' : (KIND[type] ?? 'List')}
                    </span>
                  </label>
                );
              })}
            </div>
            {visible.length === 0 && (
              <p className="text-ui text-ink-muted">Nothing matches that.</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <span className="rail-label">Custom</span>
            <div className="h-8 flex items-center gap-2 px-2.5 rounded-control border border-line-strong">
              <input
                className="flex-1 min-w-0 bg-transparent text-ui outline-none placeholder:text-ink-faint"
                placeholder="Name your own section…"
                maxLength={MAX_CUSTOM_TITLE}
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
              />
              <span className="font-mono text-micro text-ink-ghost flex-shrink-0">
                {customTitle.length}/{MAX_CUSTOM_TITLE}
              </span>
            </div>
            {customErrors.map((error) => (
              <p key={error} className="text-meta text-danger-600">
                {error}
              </p>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 p-[18px] border-t border-line-soft bg-ground-panel">
          <span className="text-meta text-ink-subtle flex-1">
            Added sections appear at the end of the CV.
          </span>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={total === 0 || add.isPending}
            onClick={() => void submit()}
          >
            {add.isPending
              ? 'Adding…'
              : `Add ${total || ''} ${total === 1 ? 'section' : 'sections'}`.replace('  ', ' ')}
          </button>
        </div>
      </div>
    </div>
  );
}
