'use client';

import { useState } from 'react';
import { useAIAvailability, useATSAnalysis } from '@/hooks/useAI';
import { Field, TextInput } from '@/components/ui/Field';
import { AIUnavailable } from './AIUnavailable';
import type { CVWithSections } from '@/types/cv';

function tone(score: number): string {
  if (score >= 75) return 'text-success-600';
  if (score >= 50) return 'text-warning-600';
  return 'text-danger-600';
}

function ScoreBar({ label, score }: { label: string; score?: number }) {
  if (typeof score !== 'number') return null;
  return (
    <div className="flex items-center gap-3">
      <span className="text-meta text-ink-muted w-28 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-line overflow-hidden">
        <div
          className="h-full rounded-full bg-accent-500"
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </div>
      <span className="font-mono text-micro tabular-nums w-8 text-right">
        {Math.round(score)}
      </span>
    </div>
  );
}

function Keywords({ title, words, muted }: { title: string; words?: string[]; muted?: boolean }) {
  if (!words?.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <span className="rail-label">{title}</span>
      <div className="flex flex-wrap gap-1.5">
        {words.map((word) => (
          <span
            key={word}
            className={`px-2 py-0.5 rounded-control text-meta border ${
              muted
                ? 'border-line-strong text-ink-muted border-dashed'
                : 'border-accent-500/40 text-accent-700 bg-accent-500/[0.06]'
            }`}
          >
            {word}
          </span>
        ))}
      </div>
    </div>
  );
}

// Keys match RecommendationPriority on the backend: high, medium, low.
const PRIORITY_STYLES: Record<string, string> = {
  high: 'border-danger-500/40 text-danger-600 bg-danger-500/[0.06]',
  medium: 'border-warning-600/40 text-warning-600 bg-warning-600/[0.06]',
  low: 'border-line-strong text-ink-muted',
};

function PriorityTag({ priority }: { priority: string }) {
  const style = PRIORITY_STYLES[priority.toLowerCase()] ?? PRIORITY_STYLES.low;
  return (
    <span className={`flex-shrink-0 rounded-control border px-1.5 py-0.5 text-micro ${style}`}>
      {priority}
    </span>
  );
}

export function ATSPanel({ cv }: { cv: CVWithSections | undefined }) {
  const { ready, reason, isLoading } = useAIAvailability();
  const analyse = useATSAnalysis(cv);
  const [industry, setIndustry] = useState('');
  const [jobTitle, setJobTitle] = useState('');

  if (isLoading) return <p className="text-ui text-ink-muted">Checking AI availability…</p>;
  if (!ready) return <AIUnavailable reason={reason ?? 'AI features are unavailable.'} />;

  const result = analyse.data;
  const score = result?.compatibility_score;

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <section className="card p-4 flex flex-col gap-3">
        <p className="text-ui text-ink-muted">
          Scores how well this CV reads to applicant tracking systems. Both fields are
          optional — they sharpen the keyword comparison.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Industry">
            {(id) => (
              <TextInput
                id={id}
                value={industry}
                placeholder="e.g. Insurance"
                onChange={(e) => setIndustry(e.target.value)}
              />
            )}
          </Field>
          <Field label="Target role">
            {(id) => (
              <TextInput
                id={id}
                value={jobTitle}
                placeholder="e.g. Director of Data Engineering"
                onChange={(e) => setJobTitle(e.target.value)}
              />
            )}
          </Field>
        </div>
        <div className="flex items-center">
          <div className="flex-1" />
          <button
            type="button"
            className="btn btn-primary"
            disabled={analyse.isPending || !cv}
            onClick={() =>
              analyse.mutate({
                industry: industry.trim() || undefined,
                job_title: jobTitle.trim() || undefined,
              })
            }
          >
            {analyse.isPending ? 'Analysing…' : result ? 'Analyse again' : 'Analyse'}
          </button>
        </div>
      </section>

      {analyse.isPending && (
        <p className="text-ui text-ink-muted">
          Working — this calls your provider and can take a minute.
        </p>
      )}

      {result && (
        <section className="flex flex-col gap-4">
          <div className="card p-4 flex items-start gap-5">
            <div className="flex flex-col flex-shrink-0">
              <span
                className={`text-3xl font-semibold tabular-nums ${tone(score?.overall_score ?? 0)}`}
              >
                {Math.round(score?.overall_score ?? 0)}
              </span>
              <span className="rail-label">Compatibility</span>
            </div>
            <p className="text-ui flex-1 min-w-0">{result.summary}</p>
          </div>

          {score && (
            <div className="card p-4 flex flex-col gap-2.5">
              <span className="rail-label">Breakdown</span>
              <ScoreBar label="Keywords" score={score.keyword_score} />
              <ScoreBar label="Formatting" score={score.formatting_score} />
              <ScoreBar label="Structure" score={score.structure_score} />
              <ScoreBar label="Completeness" score={score.completeness_score} />
            </div>
          )}

          <Keywords title="Present" words={result.present_keywords} />
          <Keywords title="Missing" words={result.missing_keywords} muted />

          {result.formatting_issues && result.formatting_issues.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="rail-label">Formatting</span>
              <ul className="card divide-y divide-line">
                {result.formatting_issues.map((issue, i) => (
                  <li key={i} className="px-3.5 py-2.5 text-ui">
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.recommendations && result.recommendations.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="rail-label">Recommendations</span>
              <ul className="card divide-y divide-line">
                {result.recommendations.map((rec, i) => (
                  <li key={i} className="flex flex-col gap-1 px-3.5 py-2.5">
                    <div className="flex items-baseline gap-2">
                      <span className="text-ui font-medium flex-1 min-w-0">
                        {rec.issue ?? rec.suggestion ?? 'Suggestion'}
                      </span>
                      {rec.priority && <PriorityTag priority={rec.priority} />}
                    </div>
                    {rec.issue && rec.suggestion && (
                      <span className="text-meta text-ink-muted">{rec.suggestion}</span>
                    )}
                    {rec.impact && (
                      <span className="text-meta text-ink-subtle">{rec.impact}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
