'use client';

import { useAIAvailability, useGrammarCheck } from '@/hooks/useAI';
import { AIUnavailable } from './AIUnavailable';
import type { GrammarIssue, Priority } from '@/lib/api';
import type { CVWithSections } from '@/types/cv';

const SEVERITY_TONE: Record<Priority, string> = {
  high: 'text-danger-600',
  medium: 'text-warning-600',
  low: 'text-ink-subtle',
};

function Issue({ issue }: { issue: GrammarIssue }) {
  return (
    <li className="flex flex-col gap-1.5 px-3.5 py-3">
      <div className="flex items-center gap-2">
        <span className={`text-[10px] leading-none ${SEVERITY_TONE[issue.severity] ?? ''}`}>
          ●
        </span>
        <span className="chip">{issue.type.replace('_', ' ')}</span>
        <span className="font-mono text-micro text-ink-faint truncate">{issue.location}</span>
      </div>

      {/* The wording as it stands, then what it should be. */}
      <p className="text-ui line-through text-ink-muted">{issue.issue_text}</p>
      <p className="text-ui font-medium text-accent-700">{issue.correction}</p>
      {issue.explanation && (
        <p className="text-meta text-ink-subtle">{issue.explanation}</p>
      )}
    </li>
  );
}

export function GrammarPanel({ cv }: { cv: CVWithSections | undefined }) {
  const { ready, reason, isLoading } = useAIAvailability();
  const check = useGrammarCheck(cv);

  if (isLoading) return <p className="text-ui text-ink-muted">Checking AI availability…</p>;
  if (!ready) return <AIUnavailable reason={reason ?? 'AI features are unavailable.'} />;

  const result = check.data;
  const issues = result?.issues ?? [];

  const counts = issues.reduce<Record<string, number>>((acc, issue) => {
    acc[issue.severity] = (acc[issue.severity] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-ui text-ink-muted flex-1 min-w-0">
          Reviews the whole CV for grammar, tense, passive voice and clarity. Nothing is
          changed automatically — corrections are suggestions to apply yourself.
        </p>
        <button
          type="button"
          className="btn btn-primary flex-shrink-0"
          disabled={check.isPending || !cv}
          onClick={() => check.mutate()}
        >
          {check.isPending ? 'Checking…' : result ? 'Check again' : 'Check writing'}
        </button>
      </div>

      {check.isPending && (
        <p className="text-ui text-ink-muted">
          Reading the whole CV — this calls your provider and can take a minute.
        </p>
      )}

      {result && issues.length === 0 && (
        <div className="alert alert-success mb-0">
          Nothing flagged{result.overall_quality ? ` — ${result.overall_quality}` : ''}.
        </div>
      )}

      {issues.length > 0 && (
        <>
          <div className="flex items-center gap-3">
            <span className="font-mono text-micro text-ink-subtle">
              {issues.length} {issues.length === 1 ? 'issue' : 'issues'}
            </span>
            {(['high', 'medium', 'low'] as Priority[]).map((severity) =>
              counts[severity] ? (
                <span key={severity} className={`font-mono text-micro ${SEVERITY_TONE[severity]}`}>
                  {counts[severity]} {severity}
                </span>
              ) : null
            )}
            {result?.overall_quality && (
              <span className="text-meta text-ink-subtle">{result.overall_quality}</span>
            )}
          </div>

          <ul className="card divide-y divide-line">
            {issues.map((issue, index) => (
              <Issue key={issue.id ?? `${issue.location}-${index}`} issue={issue} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
