'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useMemo, useState } from 'react';
import { AddSectionDialog } from '@/components/AddSectionDialog';
import { CVPreview } from '@/components/CVPreview';
import { ATSPanel } from '@/components/panels/ATSPanel';
import { ExportPanel } from '@/components/panels/ExportPanel';
import { GrammarPanel } from '@/components/panels/GrammarPanel';
import { JobMatchPanel } from '@/components/panels/JobMatchPanel';
import { StylingPanel } from '@/components/panels/StylingPanel';
import { SectionRail } from '@/components/SectionRail';
import { SectionEditor } from '@/components/editors/SectionEditor';
import { useCV } from '@/hooks/useCVs';
import { applyDrafts, useDraftStore, useHasDrafts } from '@/lib/drafts';
import { cvDisplayName, formatRelative } from '@/lib/cv-utils';
import type { Section } from '@/types/cv';

type ToolId = 'styling' | 'grammar' | 'ats' | 'match' | 'export';

const TOOLS: { id: ToolId; label: string }[] = [
  { id: 'styling', label: 'Styling' },
  { id: 'grammar', label: 'Writing' },
  { id: 'ats', label: 'ATS Score' },
  { id: 'match', label: 'Job Match' },
  { id: 'export', label: 'Export' },
];

/**
 * The CV editor.
 *
 * Deliberately ONE tree at every width. The Vue version rendered a desktop
 * layout and a narrow layout side by side and hid one with CSS, which meant
 * duplicate component instances, duplicate API calls, and a missing min-h-0
 * that made the bottom of the page unreachable below 1024px. Here the rail and
 * preview are panes that collapse into drawers; nothing is duplicated.
 */
function Editor() {
  const cvId = useSearchParams().get('id');
  const { data: cv, isLoading, isError, error } = useCV(cvId);

  const drafts = useDraftStore((s) => s.drafts);
  const clearAll = useDraftStore((s) => s.clearAll);
  const hasDrafts = useHasDrafts();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tool, setTool] = useState<ToolId | null>(null);
  const [zoom, setZoom] = useState(45);
  const [railOpen, setRailOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [addingSection, setAddingSection] = useState(false);

  // Drafts belong to one CV; leaving must not carry them to the next.
  useEffect(() => () => clearAll(), [cvId, clearAll]);

  const sections = useMemo(
    () => [...(cv?.sections ?? [])].sort((a, b) => a.order - b.order),
    [cv]
  );

  // Memoised because the preview measures its content in a layout effect keyed
  // on this array. A fresh array each render re-ran that effect every time,
  // which set state, which rendered again — a measure loop that made
  // pagination thrash and edits appear not to land.
  const drafted = useMemo(() => applyDrafts(cv, drafts), [cv, drafts]);
  const selected = sections.find((s) => s.id === selectedId) ?? null;

  const select = (section: Section) => {
    setSelectedId(section.id);
    setTool(null);
    setRailOpen(false);
  };

  const openTool = (id: ToolId) => {
    setTool(id);
    setSelectedId(null);
    setRailOpen(false);
  };

  const paneTitle = tool ? TOOLS.find((t) => t.id === tool)!.label : selected?.title ?? 'Sections';

  if (!cvId) {
    return (
      <div className="flex-1 grid place-items-center p-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <p className="font-medium">No CV selected</p>
          <Link href="/" className="btn btn-primary">
            Back to your CVs
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="h-topbar flex-shrink-0 flex items-center gap-2 sm:gap-3.5 px-3 sm:px-4 bg-surface border-b border-line">
        <Link href="/" className="btn btn-ghost btn-sm -ml-1.5 flex-shrink-0">
          <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M15 18l-6-6 6-6" />
          </svg>
          <span className="hidden sm:inline">CVs</span>
        </Link>

        <div className="w-px h-[18px] bg-line hidden sm:block" />

        <button
          type="button"
          onClick={() => setRailOpen((open) => !open)}
          className="btn btn-secondary btn-icon lg:hidden"
          aria-label="Sections"
          aria-expanded={railOpen}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>

        <span className="text-[13px] font-medium truncate px-2 py-1 rounded-control bg-ground min-w-0">
          {cv ? cvDisplayName(cv) : 'Loading…'}
        </span>

        <div className="flex-1" />

        {hasDrafts ? (
          <span className="hidden sm:flex items-center gap-1.5 text-warning-600">
            <span className="w-1.5 h-1.5 rounded-full bg-warning-400" />
            <span className="text-xs">Unsaved changes</span>
          </span>
        ) : cv ? (
          <span className="hidden md:inline text-xs text-ink-muted">
            Saved {formatRelative(cv.updated_at)}
          </span>
        ) : null}

        <button
          type="button"
          onClick={() => setPreviewOpen((open) => !open)}
          className="btn btn-secondary btn-icon xl:hidden"
          aria-label="Preview"
          aria-expanded={previewOpen}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z" />
            <circle cx="12" cy="12" r="2.6" />
          </svg>
        </button>
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden relative">
        {/* Rail: a pane at wide sizes, a drawer below lg. Same markup either way. */}
        <aside
          className={`flex-shrink-0 flex-col bg-ground-panel border-r border-line
            ${railOpen
              ? 'flex absolute inset-y-0 left-0 z-20 w-rail shadow-xl'
              : 'hidden lg:flex w-rail'}`}
        >
          <div className="flex items-center gap-2 h-9 pl-3.5 pr-2 flex-shrink-0">
            <span className="rail-label">Sections</span>
            <span className="meta-mono">{sections.length}</span>
            <div className="flex-1" />
            <button
              type="button"
              onClick={() => setAddingSection(true)}
              className="w-5 h-5 flex items-center justify-center rounded-[3px] text-ink-muted hover:bg-line-soft hover:text-ink transition-colors"
              title="Add section"
              aria-label="Add section"
            >
              <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto px-2 pb-2">
            {cv && (
              <SectionRail
                cvId={cv.id}
                sections={sections}
                selectedId={selectedId}
                onSelect={select}
              />
            )}
          </div>
          <div className="h-px bg-line mx-3 my-2 flex-shrink-0" />

          <div className="flex items-center h-6 px-3.5 flex-shrink-0">
            <span className="rail-label">Tools</span>
          </div>
          <div className="flex flex-col gap-px px-2 pb-2 flex-shrink-0">
            {TOOLS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => openTool(item.id)}
                className={`flex items-center gap-2.5 h-8 rounded-control text-ui text-left transition-colors ${
                  tool === item.id
                    ? 'pl-[7px] pr-2 bg-surface border border-line border-l-2 border-l-accent-500 font-semibold'
                    : 'px-2.5 hover:bg-line-soft'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5 h-[34px] px-3.5 border-t border-line text-ink-subtle flex-shrink-0">
            <span className="font-mono text-micro">Stored locally</span>
          </div>
        </aside>

        {railOpen && (
          <button
            type="button"
            className="absolute inset-0 z-10 bg-ink/30 lg:hidden"
            onClick={() => setRailOpen(false)}
            aria-label="Close sections"
          />
        )}

        {/* Centre: the form. min-h-0 is what keeps its bottom reachable. */}
        <div className="flex-1 min-w-0 flex flex-col bg-ground overflow-hidden">
          <div className="flex items-center gap-2.5 h-11 px-4 sm:px-6 flex-shrink-0 border-b border-line">
            <h1 className="text-[15px] font-semibold tracking-[-0.01em] truncate">
              {paneTitle}
            </h1>
            {selected && !tool && (
              <span className="chip flex-shrink-0">
                {selected.content.content_type.replace('_', ' ')}
              </span>
            )}
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto">
            <div className="p-4 sm:p-6">
              {isLoading && <p className="text-ui text-ink-muted">Loading CV…</p>}

              {isError && (
                <div className="alert alert-error">
                  {error instanceof Error ? error.message : 'Could not load this CV.'}
                </div>
              )}

              {cv && tool === 'export' && <ExportPanel cvId={cv.id} />}
              {cv && tool === 'styling' && (
                <StylingPanel cvId={cv.id} appliedId={cv.applied_template_id} />
              )}
              {cv && tool === 'grammar' && <GrammarPanel cv={cv} />}
              {cv && tool === 'ats' && <ATSPanel cv={cv} />}
              {cv && tool === 'match' && <JobMatchPanel cvId={cv.id} />}

              {cv && !selected && !tool && (
                <div className="flex flex-col items-center gap-3 py-16 text-center">
                  <svg className="w-8 h-8 text-ink-ghost" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z" />
                    <path d="M14 3v5h5M9 13h6M9 17h4" />
                  </svg>
                  <p className="text-ui text-ink-muted max-w-sm">
                    Pick a section to edit it. Changes show in the preview as you type and
                    are saved per section.
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="btn btn-secondary lg:hidden"
                      onClick={() => setRailOpen(true)}
                    >
                      Choose a section
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => setAddingSection(true)}
                    >
                      Add a section
                    </button>
                  </div>
                </div>
              )}

              {cv && selected && !tool && (
                <SectionEditor
                  key={selected.id}
                  section={selected}
                  cvId={cv.id}
                  onClose={() => setSelectedId(null)}
                />
              )}
            </div>
          </div>
        </div>

        {/* Preview: a pane at xl, a drawer below. */}
        <aside
          className={`flex-shrink-0 flex-col bg-ground-sunken border-l border-line
            ${previewOpen
              ? 'flex absolute inset-0 z-20'
              : 'hidden xl:flex w-preview'}`}
        >
          {previewOpen && (
            <button
              type="button"
              onClick={() => setPreviewOpen(false)}
              className="btn btn-secondary btn-sm m-2 self-end"
            >
              Close preview
            </button>
          )}
          <div className="flex-1 min-h-0">
            <CVPreview sections={drafted} typography={cv?.typography} zoom={zoom} onZoom={setZoom} />
          </div>
        </aside>
      </div>

      {cv && addingSection && (
        <AddSectionDialog
          cvId={cv.id}
          existing={sections}
          onClose={() => setAddingSection(false)}
        />
      )}
    </>
  );
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <Editor />
    </Suspense>
  );
}
