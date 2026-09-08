'use client';

import { useToastStore, type ToastKind } from '@/lib/toast';

const TONE: Record<ToastKind, string> = {
  success: 'alert-success',
  error: 'alert-error',
  warning: 'alert-warning',
  info: 'alert-info',
};

function Icon({ kind }: { kind: ToastKind }) {
  const path =
    kind === 'success'
      ? 'M20 6L9 17l-5-5'
      : kind === 'error'
        ? 'M12 8v5m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
        : kind === 'warning'
          ? 'M12 9v4m0 3h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z'
          : 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';

  return (
    <svg
      className="w-4 h-4 flex-shrink-0 mt-px"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-[min(24rem,calc(100vw-2rem))]"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role={t.kind === 'error' ? 'alert' : 'status'}
          className={`alert ${TONE[t.kind]} mb-0 flex items-start gap-2.5 shadow-lg`}
        >
          <Icon kind={t.kind} />
          <span className="flex-1 min-w-0">{t.message}</span>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
            aria-label="Dismiss notification"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
