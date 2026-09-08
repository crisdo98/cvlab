'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { exportApi, exportFileName, type ExportFormat, type ExportRecord } from '@/lib/api';
import { toast } from '@/lib/toast';
import { formatRelative } from '@/lib/cv-utils';
import { friendlyMessage } from '@/lib/errors';
import { Checkbox, Field, TextInput } from '@/components/ui/Field';

const FORMATS: { value: ExportFormat; label: string; blurb: string }[] = [
  { value: 'pdf', label: 'PDF', blurb: 'Print and sharing' },
  { value: 'docx', label: 'Word', blurb: 'Recruiter edits' },
  { value: 'txt', label: 'Plain text', blurb: 'ATS friendly' },
];

function formatSize(bytes?: number): string {
  if (!bytes) return '';
  return bytes < 1024 * 1024
    ? `${Math.round(bytes / 1024)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ExportPanel({ cvId }: { cvId: string }) {
  const queryClient = useQueryClient();

  const templates = useQuery({
    queryKey: ['export-templates'],
    queryFn: () => exportApi.templates(),
    staleTime: Infinity,
  });

  const history = useQuery({
    queryKey: ['export-history', cvId],
    queryFn: () => exportApi.history(cvId),
  });

  const run = useMutation({
    mutationFn: (format: ExportFormat) => exportApi.run(cvId, format),
    onSuccess: (record) => {
      queryClient.invalidateQueries({ queryKey: ['export-history', cvId] });
      toast.success(`Exported ${record.format.toUpperCase()}`);
      // The download endpoint matches on the file's name, not the export id.
      const name = exportFileName(record);
      if (name) {
        window.open(exportApi.downloadUrl(name), '_blank', 'noopener');
      } else {
        toast.error('Export finished but the file name was missing.');
      }
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Export failed'),
  });

  const remove = useMutation({
    mutationFn: (record: ExportRecord) =>
      exportApi.remove(record.format, exportFileName(record) ?? ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['export-history', cvId] });
      toast.success('Export deleted');
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Could not delete that export'),
  });

  const [withAts, setWithAts] = useState(true);
  const [withGrammar, setWithGrammar] = useState(false);
  const [industry, setIndustry] = useState('');
  const [jobDescription, setJobDescription] = useState('');

  const runReport = useMutation({
    mutationFn: (format: ExportFormat) =>
      exportApi.runWithRecommendations(cvId, format, {
        include_ats: withAts,
        include_grammar: withGrammar,
        industry: industry.trim() || undefined,
        job_description: jobDescription.trim() || undefined,
      }),
    onSuccess: (record) => {
      queryClient.invalidateQueries({ queryKey: ['export-history', cvId] });
      const name = exportFileName(record);
      if (name) {
        toast.success('Exported with recommendations');
        window.open(exportApi.downloadUrl(name), '_blank', 'noopener');
      } else {
        toast.error('Export finished but the file name was missing.');
      }
    },
    onError: (error) => toast.error(friendlyMessage(error, 'Export failed')),
  });

  const [withReport, setWithReport] = useState(false);

  // With the assessment switched on, an export needs something to assess.
  const blocked = withReport && !withAts && !withGrammar && !jobDescription.trim();
  const busy = run.isPending || runReport.isPending;

  /** One entry point: the switch decides which endpoint the format buttons hit. */
  const start = (format: ExportFormat) =>
    withReport ? runReport.mutate(format) : run.mutate(format);

  const exports = history.data?.exports ?? [];

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <section className="flex flex-col gap-3">
        <span className="rail-label">Format</span>

        {/* One set of format buttons, not two. The assessment is a switch on
            the same export rather than a second, parallel way to export. */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {FORMATS.map((format) => (
            <button
              key={format.value}
              type="button"
              disabled={busy || blocked}
              onClick={() => start(format.value)}
              className="card p-3 flex items-center gap-3 text-left hover:border-accent-500 transition-colors disabled:opacity-60"
            >
              <svg className="w-5 h-5 text-primary-600 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M14 2H7a2 2 0 00-2 2v16a2 2 0 002 2h10a2 2 0 002-2V7z" />
                <path d="M14 2v5h5" />
              </svg>
              <span className="min-w-0">
                <span className="block text-ui font-semibold">{format.label}</span>
                <span className="block text-meta text-ink-subtle">{format.blurb}</span>
              </span>
            </button>
          ))}
        </div>

        <div className="card p-4 flex flex-col gap-3">
          <Checkbox
            label="Include an assessment of this CV"
            checked={withReport}
            onChange={(e) => setWithReport(e.target.checked)}
          />
          <p className="text-meta text-ink-subtle">
            Adds the advice after the CV, starting on its own page and marked as
            private — remove it before sending the CV on. Each assessment is a
            separate model call, so the export takes a minute or two.
          </p>

          {withReport && (
            <div className="flex flex-col gap-3 pt-1">
              <div className="flex flex-col gap-1.5">
                <Checkbox
                  label="ATS assessment — scores, keywords and formatting"
                  checked={withAts}
                  onChange={(e) => setWithAts(e.target.checked)}
                />
                <Checkbox
                  label="Language check — grammar and phrasing"
                  checked={withGrammar}
                  onChange={(e) => setWithGrammar(e.target.checked)}
                />
              </div>

              <Field label="Industry" hint="Optional. Sharpens the keyword comparison.">
                {(id) => (
                  <TextInput
                    id={id}
                    value={industry}
                    placeholder="e.g. Management"
                    onChange={(e) => setIndustry(e.target.value)}
                  />
                )}
              </Field>

              <Field
                label="Job description"
                hint="Optional. Paste one to add a section on how this CV measures against that role."
              >
                {(id) => (
                  <textarea
                    id={id}
                    className="input min-h-24"
                    value={jobDescription}
                    placeholder="Paste the advert here…"
                    onChange={(e) => setJobDescription(e.target.value)}
                  />
                )}
              </Field>

              {blocked && (
                <span className="text-meta text-warning-600">
                  Choose at least one assessment, or turn this off to export the CV alone.
                </span>
              )}
            </div>
          )}
        </div>

        {busy && (
          <p className="text-meta text-ink-muted">
            {withReport
              ? 'Assessing, then rendering. This takes longer than a plain export.'
              : 'Rendering — pandoc and LaTeX run server-side, so this can take a moment.'}
          </p>
        )}
      </section>

      {templates.data && templates.data.templates.length > 1 && (
        <section className="flex flex-col gap-2">
          <span className="rail-label">Template</span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {templates.data.templates.map((template) => (
              <div key={template.template_id} className="card p-3">
                <p className="text-ui font-semibold">{template.name}</p>
                <p className="text-meta text-ink-subtle">{template.description}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="flex flex-col gap-2">
        <span className="rail-label">Recent exports</span>
        {history.isLoading && <p className="text-ui text-ink-muted">Loading…</p>}
        {!history.isLoading && exports.length === 0 && (
          <p className="text-ui text-ink-muted">Nothing exported yet.</p>
        )}
        {exports.length > 0 && (
          <ul className="card divide-y divide-line">
            {exports.slice(0, 8).map((record) => (
              <li key={record.export_id} className="flex items-center gap-3 px-3 h-10">
                <span className="chip flex-shrink-0">{record.format}</span>
                <span className="flex-1 min-w-0 font-mono text-[12px] truncate">
                  {record.file_name}
                </span>
                {record.created_at && (
                  <span className="text-meta text-ink-subtle hidden sm:inline">
                    {formatRelative(record.created_at)}
                  </span>
                )}
                <span className="font-mono text-micro text-ink-faint hidden sm:inline">
                  {formatSize(record.file_size)}
                </span>
                <a
                  href={exportApi.downloadUrl(exportFileName(record) ?? '')}
                  target="_blank"
                  rel="noopener"
                  className="btn btn-sm btn-secondary flex-shrink-0"
                >
                  Download
                </a>
                <button
                  type="button"
                  onClick={() => remove.mutate(record)}
                  disabled={remove.isPending}
                  aria-label={`Delete ${record.file_name}`}
                  title="Delete this export"
                  className="w-6 h-6 flex-shrink-0 flex items-center justify-center rounded-[3px] text-ink-subtle hover:text-danger-600 hover:bg-line-soft disabled:opacity-40"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
