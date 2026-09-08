'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { backupApi, type BackupInfo } from '@/lib/api';
import { Checkbox } from '@/components/ui/Field';
import { formatDateTime } from '@/lib/cv-utils';
import { toast } from '@/lib/toast';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function BackupPage() {
  const queryClient = useQueryClient();
  const [includeExports, setIncludeExports] = useState(false);
  const [restoring, setRestoring] = useState<BackupInfo | null>(null);
  const [confirmText, setConfirmText] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);

  const backups = useQuery({ queryKey: ['backups'], queryFn: () => backupApi.list() });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['backups'] });

  const create = useMutation({
    mutationFn: () => backupApi.create(includeExports),
    onSuccess: (result) => {
      invalidate();
      toast.success(`Backup created — ${result.filename}`);
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Backup failed'),
  });

  const restore = useMutation({
    mutationFn: (filename: string) => backupApi.restore(filename),
    onSuccess: () => {
      // Everything on screen may now be stale.
      queryClient.invalidateQueries();
      setRestoring(null);
      setConfirmText('');
      toast.success('Backup restored');
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Restore failed'),
  });

  const remove = useMutation({
    mutationFn: (filename: string) => backupApi.remove(filename),
    onSuccess: () => {
      invalidate();
      setDeleting(null);
      toast.success('Backup deleted');
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Could not delete that backup'),
  });

  const list = backups.data?.backups ?? [];

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <header className="flex flex-wrap items-center gap-3">
        <div className="flex flex-col gap-0.5">
          <h1 className="text-xl font-semibold tracking-[-0.01em]">Backup and restore</h1>
          <p className="text-ui text-ink-muted">
            {list.length} {list.length === 1 ? 'backup' : 'backups'} stored on this machine
          </p>
        </div>
        <div className="flex-1" />
        <Checkbox
          label="Include exports"
          checked={includeExports}
          onChange={(e) => setIncludeExports(e.target.checked)}
        />
        <button
          type="button"
          className="btn btn-primary"
          disabled={create.isPending}
          onClick={() => create.mutate()}
        >
          {create.isPending ? 'Creating…' : 'Create backup'}
        </button>
      </header>

      {backups.isError && (
        <div className="alert alert-error">Could not load your backups.</div>
      )}

      {backups.isLoading && <p className="text-ui text-ink-muted">Loading…</p>}

      {!backups.isLoading && list.length === 0 && (
        <div className="card flex flex-col items-center gap-3 py-14 px-6 text-center">
          <svg className="w-8 h-8 text-ink-ghost" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M21 8v11a2 2 0 01-2 2H5a2 2 0 01-2-2V8M3 8l2-5h14l2 5M3 8h18M10 12h4" />
          </svg>
          <div className="flex flex-col gap-1">
            <p className="font-medium">No backups yet</p>
            <p className="text-ui text-ink-muted">
              A backup captures your CVs and applications as a single file you can restore later.
            </p>
          </div>
        </div>
      )}

      {list.length > 0 && (
        <ul className="card divide-y divide-line">
          {list.map((backup) => (
            <li key={backup.filename} className="flex flex-col">
              <div className="flex items-center gap-3 px-3.5 h-12">
                <span className="flex-1 min-w-0">
                  <span className="block font-mono text-[12px] truncate">
                    {backup.filename}
                  </span>
                  <span className="block text-meta text-ink-subtle">
                    {formatDateTime(backup.created_at)} · {formatSize(backup.size)}
                    {backup.version ? ` · v${backup.version}` : ''}
                  </span>
                </span>

                <a
                  href={backupApi.downloadUrl(backup.filename)}
                  className="btn btn-sm btn-secondary flex-shrink-0"
                >
                  Download
                </a>
                <button
                  type="button"
                  className="btn btn-sm btn-secondary flex-shrink-0"
                  onClick={() => {
                    setRestoring(backup);
                    setConfirmText('');
                  }}
                >
                  Restore
                </button>
                <button
                  type="button"
                  className="w-7 h-7 flex-shrink-0 flex items-center justify-center rounded-control text-ink-faint hover:bg-danger-50 hover:text-danger-600 transition-colors"
                  aria-label={`Delete ${backup.filename}`}
                  onClick={() => setDeleting(backup.filename)}
                >
                  <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
                  </svg>
                </button>
              </div>

              {deleting === backup.filename && (
                <div className="flex items-center gap-2 px-3.5 pb-3">
                  <span className="text-meta text-ink-muted flex-1">Delete this backup file?</span>
                  <button type="button" className="btn btn-sm btn-secondary" onClick={() => setDeleting(null)}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    onClick={() => remove.mutate(backup.filename)}
                  >
                    Delete
                  </button>
                </div>
              )}

              {/* Restore replaces live data, so it asks for the filename to be typed
                  rather than accepting a single misclick. */}
              {restoring?.filename === backup.filename && (
                <div className="flex flex-col gap-2 px-3.5 pb-3.5">
                  <div className="alert alert-warning mb-0">
                    Restoring replaces your current CVs and applications with the contents of
                    this backup. It cannot be undone.
                  </div>
                  <label className="text-meta text-ink-muted" htmlFor="confirm-restore">
                    Type the filename to confirm
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      id="confirm-restore"
                      className="input flex-1 font-mono"
                      value={confirmText}
                      placeholder={backup.filename}
                      onChange={(e) => setConfirmText(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setRestoring(null);
                        setConfirmText('');
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger"
                      disabled={confirmText.trim() !== backup.filename || restore.isPending}
                      onClick={() => restore.mutate(backup.filename)}
                    >
                      {restore.isPending ? 'Restoring…' : 'Restore'}
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
