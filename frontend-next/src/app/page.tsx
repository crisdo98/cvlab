'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';
import {
  useCVList,
  useCreateCV,
  useDeleteCV,
  useDuplicateCV,
  useImportMarkdown,
} from '@/hooks/useCVs';
import { cvDisplayName, cvSubtitle, formatRelative, visibleSectionCount } from '@/lib/cv-utils';
import { toast } from '@/lib/toast';
import { AIImportDialog } from '@/components/AIImportDialog';

function Spinner({ className = 'w-3.5 h-3.5' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

export default function CVListPage() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);

  const { data: cvs, isLoading, isError, error, refetch, isFetching } = useCVList();
  const createCV = useCreateCV();
  const deleteCV = useDeleteCV();
  const duplicateCV = useDuplicateCV();
  const importCV = useImportMarkdown();

  // Delete confirms inline on the row rather than in a modal.
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  const handleCreate = async () => {
    const cv = await createCV.mutateAsync({});
    router.push(`/cv/?id=${cv.id}`);
  };

  const [aiOpen, setAiOpen] = useState(false);

  const handleImport = async (file: File | undefined) => {
    if (!file) return;
    if (!/\.(md|markdown|txt)$/i.test(file.name)) {
      toast.error('Choose a Markdown file (.md)');
      return;
    }
    const cv = await importCV.mutateAsync({ file });
    router.push(`/cv/?id=${cv.id}`);
  };

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center gap-3">
        <div className="flex flex-col gap-0.5">
          <h1 className="text-xl font-semibold tracking-[-0.01em]">Your CVs</h1>
          <p className="text-ui text-ink-muted">
            {cvs ? `${cvs.length} ${cvs.length === 1 ? 'document' : 'documents'}` : ' '}
          </p>
        </div>

        <div className="flex-1" />

        <button
          type="button"
          onClick={() => refetch()}
          className="btn btn-secondary btn-icon"
          title="Refresh"
          disabled={isFetching}
        >
          {isFetching ? (
            <Spinner className="w-4 h-4" />
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 12a9 9 0 0115.5-6.2M21 12a9 9 0 01-15.5 6.2M18 3v4h-4M6 21v-4h4" />
            </svg>
          )}
        </button>

        <input
          ref={fileInput}
          type="file"
          accept=".md,.markdown,text/markdown"
          className="hidden"
          onChange={(event) => {
            void handleImport(event.target.files?.[0]);
            event.target.value = '';
          }}
        />
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="btn btn-secondary"
          disabled={importCV.isPending}
        >
          {importCV.isPending ? <Spinner /> : (
            <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 9l5-5 5 5M12 4v12" />
            </svg>
          )}
          Import Markdown
        </button>

        <button
          type="button"
          onClick={() => setAiOpen(true)}
          className="btn btn-secondary"
          title="Read any CV text with the AI assistant"
        >
          <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5 10.1 10.9 5.5 9l4.6-1.4L12 3zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z" />
          </svg>
          Import with AI
        </button>

        <button
          type="button"
          onClick={() => void handleCreate()}
          className="btn btn-primary"
          disabled={createCV.isPending}
        >
          {createCV.isPending ? <Spinner /> : (
            <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 5v14M5 12h14" />
            </svg>
          )}
          New CV
        </button>
      </header>

      {isError && (
        <div className="alert alert-error flex items-start gap-2.5">
          <span className="flex-1">
            {error instanceof Error ? error.message : 'Could not load your CVs.'}
          </span>
          <button type="button" onClick={() => refetch()} className="btn btn-sm btn-secondary">
            Retry
          </button>
        </div>
      )}

      {isLoading && (
        <div className="card divide-y divide-line" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-4 px-4 h-14">
              <div className="h-3.5 w-48 rounded bg-line-soft animate-pulse" />
              <div className="flex-1" />
              <div className="h-3 w-24 rounded bg-line-soft animate-pulse" />
            </div>
          ))}
        </div>
      )}

      {!isLoading && !isError && cvs?.length === 0 && (
        <div className="card flex flex-col items-center gap-3 py-14 px-6 text-center">
          <svg className="w-8 h-8 text-ink-ghost" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z" />
            <path d="M14 3v5h5M9 13h6M9 17h4" />
          </svg>
          <div className="flex flex-col gap-1">
            <p className="font-medium">No CVs yet</p>
            <p className="text-ui text-ink-muted">
              Start one from scratch, or import an existing Markdown CV.
            </p>
          </div>
          <button type="button" onClick={() => void handleCreate()} className="btn btn-primary">
            New CV
          </button>
        </div>
      )}

      {!isLoading && cvs && cvs.length > 0 && (
        <ul className="card divide-y divide-line">
          {cvs.map((cv) => {
            const name = cvDisplayName(cv);
            const role = cvSubtitle(cv);
            const confirming = confirmingId === cv.id;

            return (
              <li key={cv.id} className="flex items-center gap-3 px-4 h-14">
                <Link
                  href={`/cv/?id=${cv.id}`}
                  className="flex-1 min-w-0 flex items-baseline gap-2.5 group"
                >
                  <span className="font-medium truncate group-hover:text-accent-700 transition-colors">
                    {name}
                  </span>
                  {role && <span className="text-ui text-ink-muted truncate">{role}</span>}
                </Link>

                <span className="meta-mono hidden sm:inline">
                  {visibleSectionCount(cv)}{' '}
                  {visibleSectionCount(cv) === 1 ? 'section' : 'sections'}
                </span>
                <span className="text-meta text-ink-subtle hidden md:inline w-32 text-right">
                  {formatRelative(cv.updated_at)}
                </span>

                {confirming ? (
                  <span className="flex items-center gap-1.5">
                    <span className="text-meta text-ink-muted hidden sm:inline">Delete?</span>
                    <button
                      type="button"
                      className="btn btn-sm btn-secondary"
                      onClick={() => setConfirmingId(null)}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm btn-danger"
                      disabled={deleteCV.isPending}
                      onClick={async () => {
                        await deleteCV.mutateAsync(cv.id);
                        setConfirmingId(null);
                      }}
                    >
                      Delete
                    </button>
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5">
                    <button
                      type="button"
                      onClick={() => void duplicateCV.mutateAsync(cv.id)}
                      disabled={duplicateCV.isPending}
                      className="w-7 h-7 flex items-center justify-center rounded-control text-ink-faint hover:bg-line-soft hover:text-ink transition-colors disabled:opacity-40"
                      title={`Duplicate ${name}`}
                      aria-label={`Duplicate ${name}`}
                    >
                      <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                        <rect x="9" y="9" width="11" height="11" rx="2" />
                        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmingId(cv.id)}
                      className="w-7 h-7 flex items-center justify-center rounded-control text-ink-faint hover:bg-danger-50 hover:text-danger-600 transition-colors"
                      title={`Delete ${name}`}
                      aria-label={`Delete ${name}`}
                    >
                      <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
                      </svg>
                    </button>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    <AIImportDialog
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        onCreated={(id) => {
          setAiOpen(false);
          router.push(`/cv/?id=${id}`);
        }}
      />
    </div>
  );
}
