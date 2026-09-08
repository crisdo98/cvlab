'use client';

import { useState } from 'react';
import { KanbanBoard } from '@/components/KanbanBoard';
import { Field, TextArea, TextInput } from '@/components/ui/Field';
import { STAGES } from '@/components/KanbanBoard';
import {
  useApplications,
  useCreateApplication,
  useDeleteApplication,
  useMoveApplication,
  useUpdateApplication,
} from '@/hooks/useApplications';
import { formatDateTime } from '@/lib/cv-utils';
import { Stage, type Application } from '@/types/applicationTracker';

function ApplicationDialog({
  application,
  onClose,
}: {
  application: Application;
  onClose: () => void;
}) {
  const update = useUpdateApplication();
  const remove = useDeleteApplication();
  const move = useMoveApplication();
  const [confirming, setConfirming] = useState(false);

  const [form, setForm] = useState({
    company_name: application.company_name,
    position_title: application.position_title,
    job_description_url: application.job_description_url ?? '',
    recruiter_name: application.recruiter_name ?? '',
    recruiter_email: application.recruiter_email ?? '',
    notes: application.notes ?? '',
  });

  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 overflow-y-auto"
      style={{ background: 'rgb(22 32 43 / 0.34)' }}
    >
      <div className="w-full max-w-xl my-8 card rounded-dialog shadow-2xl flex flex-col">
        <div className="flex items-center gap-2 h-12 pl-[18px] pr-3 border-b border-line-soft flex-shrink-0">
          <h2 className="text-[15px] font-semibold tracking-[-0.01em] truncate">
            {application.position_title}
          </h2>
          <div className="flex-1" />
          <label className="sr-only" htmlFor="stage-select">
            Stage
          </label>
          <select
            id="stage-select"
            className="input w-auto"
            value={application.stage}
            onChange={(e) => move.mutate({ id: application.id, stage: e.target.value as Stage })}
          >
            {STAGES.map((stage) => (
              <option key={stage.id} value={stage.id}>
                {stage.label}
              </option>
            ))}
          </select>
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

        <div className="p-[18px] flex flex-col gap-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Company" required>
              {(id) => (
                <TextInput
                  id={id}
                  value={form.company_name}
                  onChange={(e) => set({ company_name: e.target.value })}
                />
              )}
            </Field>
            <Field label="Position" required>
              {(id) => (
                <TextInput
                  id={id}
                  value={form.position_title}
                  onChange={(e) => set({ position_title: e.target.value })}
                />
              )}
            </Field>
          </div>

          <Field label="Job advert URL">
            {(id) => (
              <TextInput
                id={id}
                value={form.job_description_url}
                placeholder="https://"
                onChange={(e) => set({ job_description_url: e.target.value })}
              />
            )}
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Recruiter">
              {(id) => (
                <TextInput
                  id={id}
                  value={form.recruiter_name}
                  onChange={(e) => set({ recruiter_name: e.target.value })}
                />
              )}
            </Field>
            <Field label="Recruiter email">
              {(id) => (
                <TextInput
                  id={id}
                  type="email"
                  value={form.recruiter_email}
                  onChange={(e) => set({ recruiter_email: e.target.value })}
                />
              )}
            </Field>
          </div>

          <Field label="Notes">
            {(id) => (
              <TextArea
                id={id}
                rows={5}
                value={form.notes}
                onChange={(e) => set({ notes: e.target.value })}
              />
            )}
          </Field>

          <p className="font-mono text-micro text-ink-faint">
            Applied {formatDateTime(application.application_date)} · updated{' '}
            {formatDateTime(application.updated_at)}
          </p>
        </div>

        <div className="flex items-center gap-2 p-[18px] border-t border-line-soft bg-ground-panel flex-shrink-0">
          {confirming ? (
            <>
              <span className="text-meta text-ink-muted flex-1">Delete this application?</span>
              <button type="button" className="btn btn-secondary" onClick={() => setConfirming(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={async () => {
                  await remove.mutateAsync(application.id);
                  onClose();
                }}
              >
                Delete
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="btn btn-ghost text-danger-600"
                onClick={() => setConfirming(true)}
              >
                Delete
              </button>
              <div className="flex-1" />
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={update.isPending}
                onClick={async () => {
                  await update.mutateAsync({
                    id: application.id,
                    payload: {
                      ...form,
                      job_description_url: form.job_description_url || undefined,
                      recruiter_name: form.recruiter_name || undefined,
                      recruiter_email: form.recruiter_email || undefined,
                      notes: form.notes || undefined,
                    },
                  });
                  onClose();
                }}
              >
                {update.isPending ? 'Saving…' : 'Save'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function NewApplicationRow({ onDone }: { onDone: () => void }) {
  const create = useCreateApplication();
  const [company, setCompany] = useState('');
  const [position, setPosition] = useState('');

  const submit = async () => {
    if (!company.trim() || !position.trim()) return;
    await create.mutateAsync({
      company_name: company.trim(),
      position_title: position.trim(),
      stage: Stage.WISHLIST,
      application_date: new Date().toISOString(),
    });
    onDone();
  };

  return (
    <div className="card p-3 flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
      <div className="flex-1">
        <Field label="Company" required>
          {(id) => (
            <TextInput
              id={id}
              autoFocus
              value={company}
              onChange={(e) => setCompany(e.target.value)}
            />
          )}
        </Field>
      </div>
      <div className="flex-1">
        <Field label="Position" required>
          {(id) => (
            <TextInput
              id={id}
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void submit()}
            />
          )}
        </Field>
      </div>
      <div className="flex items-center gap-2">
        <button type="button" className="btn btn-secondary" onClick={onDone}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!company.trim() || !position.trim() || create.isPending}
          onClick={() => void submit()}
        >
          {create.isPending ? 'Adding…' : 'Add'}
        </button>
      </div>
    </div>
  );
}

export default function ApplicationsPage() {
  const { data: applications, isLoading, isError, error } = useApplications();
  const move = useMoveApplication();
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState<Application | null>(null);

  const list = applications ?? [];
  const active = list.filter((a) => a.stage !== Stage.REJECTED).length;

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center gap-3">
        <div className="flex flex-col gap-0.5">
          <h1 className="text-xl font-semibold tracking-[-0.01em]">Applications</h1>
          <p className="text-ui text-ink-muted">
            {list.length} tracked · {active} active
          </p>
        </div>
        <div className="flex-1" />
        <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
          <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Track a role
        </button>
      </header>

      {adding && <NewApplicationRow onDone={() => setAdding(false)} />}

      {isError && (
        <div className="alert alert-error">
          {error instanceof Error ? error.message : 'Could not load applications.'}
        </div>
      )}

      {isLoading && <p className="text-ui text-ink-muted">Loading board…</p>}

      {!isLoading && !isError && list.length === 0 && !adding && (
        <div className="card flex flex-col items-center gap-3 py-14 px-6 text-center">
          <svg className="w-8 h-8 text-ink-ghost" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="5" width="18" height="16" rx="2" />
            <path d="M3 10h18M8 3v4M16 3v4" />
          </svg>
          <div className="flex flex-col gap-1">
            <p className="font-medium">No applications tracked</p>
            <p className="text-ui text-ink-muted">
              Add a role to start moving it through the stages.
            </p>
          </div>
          <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
            Track a role
          </button>
        </div>
      )}

      {!isLoading && list.length > 0 && (
        <KanbanBoard
          applications={list}
          onMove={(id, stage) => move.mutate({ id, stage })}
          onOpen={setOpen}
        />
      )}

      {open && <ApplicationDialog application={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
