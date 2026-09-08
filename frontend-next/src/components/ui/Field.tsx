'use client';

import { forwardRef, useEffect, useId, useRef } from 'react';

/**
 * Shared form primitives. In the Vue app every editor carried its own private
 * copies of these styles — 17 components each redefining .field-input, which is
 * how they drifted away from the design system. Here there is one of each.
 */

interface FieldProps {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: (id: string) => React.ReactNode;
}

export function Field({ label, required, hint, error, children }: FieldProps) {
  const id = useId();

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="flex items-center gap-1.5 text-meta font-medium text-ink-muted">
        {label}
        {required && (
          <span className="font-mono text-[9.5px] uppercase tracking-[0.05em] text-ink-faint">
            required
          </span>
        )}
      </label>
      {children(id)}
      {error ? (
        <p className="text-meta text-danger-600">{error}</p>
      ) : hint ? (
        <p className="text-meta text-ink-subtle">{hint}</p>
      ) : null}
    </div>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input type="text" {...props} className={`input ${props.className ?? ''}`} />;
}

// Forwards its ref so a toolbar can read the selection and restore the caret.
export const TextArea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function TextArea(props, ref) {
  return (
    <textarea
      ref={ref}
      {...props}
      className={`w-full px-2.5 py-2 rounded-control text-ui leading-relaxed resize-y
        bg-surface text-ink border border-line-strong placeholder:text-ink-faint
        focus:outline-none focus:border-accent-500 focus:ring-[3px] focus:ring-accent-500/15
        transition-colors duration-150 ${props.className ?? ''}`}
    />
  );
});

/**
 * A textarea that grows to fit its content, so a long CV bullet is readable
 * instead of truncating inside a one-line input.
 */
export function AutoGrowTextArea({
  value,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { value: string }) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      rows={1}
      value={value}
      {...props}
      className={`flex-1 min-w-0 px-2.5 py-1.5 rounded-control text-ui leading-relaxed
        resize-none overflow-hidden
        bg-surface text-ink border border-line-strong placeholder:text-ink-faint
        focus:outline-none focus:border-accent-500 focus:ring-[3px] focus:ring-accent-500/15
        transition-colors duration-150 ${props.className ?? ''}`}
    />
  );
}

export function Checkbox({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-ui cursor-pointer">
      <input
        id={id}
        type="checkbox"
        {...props}
        className="w-[15px] h-[15px] rounded-[3px] border-ink-ghost text-accent-500
          focus:ring-2 focus:ring-accent-500/30 cursor-pointer"
      />
      {label}
    </label>
  );
}

export function IconButton({
  label,
  tone = 'neutral',
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  tone?: 'neutral' | 'danger';
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      {...props}
      className={`w-6 h-6 flex-shrink-0 flex items-center justify-center rounded-[3px]
        text-ink-faint transition-colors disabled:opacity-40
        ${tone === 'danger' ? 'hover:bg-danger-50 hover:text-danger-600' : 'hover:bg-line-soft hover:text-ink'}
        ${props.className ?? ''}`}
    >
      {children}
    </button>
  );
}

export function AddButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center gap-1.5 h-7 px-2.5 self-start
        rounded-control border border-dashed border-line-strong
        text-meta text-ink-muted hover:border-accent-500 hover:text-accent-700
        transition-colors ${props.className ?? ''}`}
    >
      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 5v14M5 12h14" />
      </svg>
      {children}
    </button>
  );
}
