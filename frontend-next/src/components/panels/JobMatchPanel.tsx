'use client';

import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { jobApi } from '@/lib/api';
import { Field, TextArea, TextInput } from '@/components/ui/Field';
import { toast } from '@/lib/toast';

interface Criterion {
  criterion: string;
  status: string;
  explanation?: string;
  importance?: string;
}

interface Category {
  category: string;
  criteria: Criterion[];
  category_score?: number;
}

interface SuitabilityResult {
  overall_score?: number;
  recommendation?: string;
  categories?: Category[];
  criteria_met?: number;
  criteria_partial?: number;
  criteria_not_met?: number;
  total_criteria?: number;
  key_strengths?: string[];
  critical_gaps?: string[];
  improvement_suggestions?: string[];
}

function scoreTone(score: number): string {
  if (score >= 75) return 'text-success-600';
  if (score >= 50) return 'text-warning-600';
  return 'text-danger-600';
}

function statusMark(status: string) {
  const s = status.toLowerCase();
  if (s.includes('met') && !s.includes('not')) return { glyph: '●', tone: 'text-success-600' };
  if (s.includes('partial')) return { glyph: '◐', tone: 'text-warning-600' };
  return { glyph: '○', tone: 'text-danger-600' };
}

export function JobMatchPanel({ cvId }: { cvId: string }) {
  const [jobTitle, setJobTitle] = useState('');
  const [description, setDescription] = useState('');

  const analyse = useMutation({
    mutationFn: async () => {
      const response = (await jobApi.analyse({
        cv_id: cvId,
        job_description: description,
        job_title: jobTitle || undefined,
        include_improvement_suggestions: true,
      })) as { result?: SuitabilityResult };
      return response.result ?? (response as SuitabilityResult);
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Could not analyse that job'),
  });

  const result = analyse.data;

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <section className="card p-4 flex flex-col gap-3">
        <Field label="Job title">
          {(id) => (
            <TextInput
              id={id}
              value={jobTitle}
              placeholder="e.g. Director of Data Engineering"
              onChange={(e) => setJobTitle(e.target.value)}
            />
          )}
        </Field>

        <Field
          label="Job description"
          required
          hint="Paste the advert. It is sent to your configured AI provider."
        >
          {(id) => (
            <TextArea
              id={id}
              rows={10}
              value={description}
              placeholder="Paste the full job description…"
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </Field>

        <div className="flex items-center gap-2">
          <span className="font-mono text-micro text-ink-faint">
            {description.trim() ? description.trim().split(/\s+/).length : 0} words
          </span>
          <div className="flex-1" />
          <button
            type="button"
            className="btn btn-primary"
            disabled={description.trim().length < 40 || analyse.isPending}
            onClick={() => analyse.mutate()}
          >
            {analyse.isPending ? 'Analysing…' : 'Analyse fit'}
          </button>
        </div>
        {description.trim().length > 0 && description.trim().length < 40 && (
          <p className="text-meta text-ink-subtle">
            Paste a bit more of the advert for a useful result.
          </p>
        )}
      </section>

      {analyse.isPending && (
        <p className="text-ui text-ink-muted">
          Working — this calls your AI provider and can take a minute.
        </p>
      )}

      {result && (
        <section className="flex flex-col gap-4">
          <div className="card p-4 flex items-center gap-5">
            <div className="flex flex-col">
              <span
                className={`text-3xl font-semibold tabular-nums ${scoreTone(result.overall_score ?? 0)}`}
              >
                {Math.round(result.overall_score ?? 0)}
              </span>
              <span className="rail-label">Overall</span>
            </div>
            <div className="flex-1 min-w-0">
              {result.recommendation && (
                <p className="text-ui font-medium mb-1">{result.recommendation}</p>
              )}
              <p className="font-mono text-micro text-ink-subtle">
                {result.criteria_met ?? 0} met · {result.criteria_partial ?? 0} partial ·{' '}
                {result.criteria_not_met ?? 0} not met
                {result.total_criteria ? ` · ${result.total_criteria} criteria` : ''}
              </p>
            </div>
          </div>

          {result.key_strengths && result.key_strengths.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="rail-label">Strengths</span>
              <ul className="card divide-y divide-line">
                {result.key_strengths.map((item, i) => (
                  <li key={i} className="px-3.5 py-2.5 text-ui">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.critical_gaps && result.critical_gaps.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="rail-label">Gaps</span>
              <ul className="card divide-y divide-line">
                {result.critical_gaps.map((item, i) => (
                  <li key={i} className="px-3.5 py-2.5 text-ui">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.categories?.map((category) => (
            <div key={category.category} className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className="rail-label">{category.category}</span>
                {typeof category.category_score === 'number' && (
                  <span className="font-mono text-micro text-ink-faint tabular-nums">
                    {Math.round(category.category_score)}
                  </span>
                )}
              </div>
              <ul className="card divide-y divide-line">
                {category.criteria.map((criterion, i) => {
                  const mark = statusMark(criterion.status);
                  return (
                    <li key={i} className="flex items-start gap-2.5 px-3.5 py-2.5">
                      <span className={`${mark.tone} leading-none pt-1`}>{mark.glyph}</span>
                      <span className="min-w-0">
                        <span className="block text-ui">{criterion.criterion}</span>
                        {criterion.explanation && (
                          <span className="block text-meta text-ink-subtle">
                            {criterion.explanation}
                          </span>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}

          {result.improvement_suggestions && result.improvement_suggestions.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="rail-label">Suggestions</span>
              <ul className="card divide-y divide-line">
                {result.improvement_suggestions.map((item, i) => (
                  <li key={i} className="px-3.5 py-2.5 text-ui">
                    {item}
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
