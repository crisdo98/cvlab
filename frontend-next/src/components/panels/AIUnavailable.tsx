'use client';

import Link from 'next/link';

/**
 * Shown wherever an AI feature cannot run. It names the actual reason rather
 * than leaving a dead button, and links to the setting that fixes it.
 */
export function AIUnavailable({ reason }: { reason: string }) {
  return (
    <div className="card flex flex-col items-start gap-3 p-5 max-w-xl">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-ink-faint" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3l2.1 5.4L19.5 10l-5.4 2.1L12 17.5l-2.1-5.4L4.5 10l5.4-1.6z" />
        </svg>
        <p className="font-medium">AI is not available</p>
      </div>
      <p className="text-ui text-ink-muted">{reason}</p>
      <Link href="/settings/llm/" className="btn btn-secondary">
        Open AI settings
      </Link>
    </div>
  );
}
