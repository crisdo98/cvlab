'use client';

import { useToastStore } from '@/lib/toast';

/**
 * Proof sheet: renders the ported design system so the tokens can be
 * checked against the Vue app before any screens are built on top of them.
 * Replaced by the real CV list in Phase 2.
 */
export default function TokensPage() {
  return (
    <main className="min-h-screen p-10 max-w-4xl mx-auto flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <span className="rail-label">Phase 0</span>
        <h1 className="text-2xl font-semibold tracking-[-0.01em]">
          CVLab design system
        </h1>
        <p className="text-ui text-ink-muted">
          Ported from the Vue app. Navy <code className="font-mono">#1d4a6e</code> and teal{' '}
          <code className="font-mono">#2fa295</code>, both taken from the logo mark.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <span className="rail-label">Buttons</span>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn btn-primary">Save</button>
          <button className="btn btn-secondary">Export</button>
          <button className="btn btn-accent">Bulk edit</button>
          <button className="btn btn-ghost">Close section</button>
          <button className="btn btn-danger">Delete</button>
          <button className="btn btn-secondary" disabled>
            Disabled
          </button>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <span className="rail-label">Controls</span>
        <div className="card p-5 flex flex-col gap-4 max-w-md">
          <div className="flex items-center gap-2.5">
            <h2 className="text-[15px] font-semibold tracking-[-0.01em]">
              Work Experience
            </h2>
            <span className="chip">Structured</span>
          </div>
          <div>
            <label className="field-label" htmlFor="demo-title">
              Job title
            </label>
            <input
              id="demo-title"
              className="input"
              defaultValue="Head of Data Engineering"
            />
          </div>
          <div>
            <label className="field-label" htmlFor="demo-notes">
              Description
            </label>
            <textarea id="demo-notes" className="input" rows={3} placeholder="One per line" />
          </div>
          <p className="meta-mono">Stored locally &middot; 4 CVs</p>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <span className="rail-label">Palette</span>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            ['Navy 600', 'bg-primary-600'],
            ['Navy 700', 'bg-primary-700'],
            ['Teal 500', 'bg-accent-500'],
            ['Teal 700', 'bg-accent-700'],
            ['Ground', 'bg-ground'],
            ['Panel', 'bg-ground-panel'],
            ['Sunken', 'bg-ground-sunken'],
            ['Line', 'bg-line-strong'],
          ].map(([label, cls]) => (
            <div key={label} className="flex flex-col gap-1.5">
              <div className={`h-12 rounded-control border border-line ${cls}`} />
              <span className="meta-mono">{label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <span className="rail-label">Toasts</span>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-secondary" onClick={() => useToastStore.getState().success('Section order updated')}>Success</button>
          <button className="btn btn-secondary" onClick={() => useToastStore.getState().error('Failed to update section')}>Error (persists)</button>
          <button className="btn btn-secondary" onClick={() => useToastStore.getState().warning('Unsaved changes')}>Warning</button>
          <button className="btn btn-secondary" onClick={() => useToastStore.getState().info('Preview reflects unsaved edits')}>Info</button>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <span className="rail-label">Alerts</span>
        <div className="alert alert-info">Preview reflects unsaved edits.</div>
        <div className="alert alert-warning">Unsaved changes.</div>
        <div className="alert alert-error">Failed to update section.</div>
      </section>
    </main>
  );
}
