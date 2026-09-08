'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { typographyApi, type TypographyTemplate } from '@/lib/api';
import { cvKeys } from '@/hooks/useCVs';
import { toast } from '@/lib/toast';
import { friendlyMessage } from '@/lib/errors';
import { Field, TextInput } from '@/components/ui/Field';
import { TypographyEditor } from '@/components/panels/TypographyEditor';

/** Reads the heading/body faces out of a template's typography blob. */
function faces(template: TypographyTemplate): { heading: string; body: string } {
  const t = template.typography as Record<string, { font_family?: string }>;
  return {
    heading: t?.h1_style?.font_family ?? '—',
    body: t?.body_style?.font_family ?? t?.h2_style?.font_family ?? '—',
  };
}

export function StylingPanel({ cvId, appliedId }: { cvId: string; appliedId?: string | null }) {
  const queryClient = useQueryClient();

  const templates = useQuery({
    queryKey: ['typography-templates'],
    queryFn: () => typographyApi.templates(),
    staleTime: Infinity,
  });

  const apply = useMutation({
    mutationFn: (templateId: string) => typographyApi.applyTemplate(cvId, templateId),
    onSuccess: (_data, templateId) => {
      queryClient.invalidateQueries({ queryKey: cvKeys.detail(cvId) });
      toast.success(`Applied ${templateId}`);
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Could not apply that template'),
  });

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const save = useMutation({
    mutationFn: async () => {
      // Save what this CV is actually using, so the template captures any
      // adjustment made since a stock template was applied.
      const typography = await typographyApi.forCV(cvId);
      const config = (typography as { typography?: Record<string, unknown> }).typography
        ?? (typography as Record<string, unknown>);
      return typographyApi.saveTemplate(name.trim(), description.trim() || name.trim(), config);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['typography-templates'] });
      setName('');
      setDescription('');
      toast.success('Template saved');
    },
    onError: (error) => toast.error(friendlyMessage(error, 'Could not save that template')),
  });

  return (
    <div className="flex flex-col gap-3 max-w-3xl">
      <span className="rail-label">Typography</span>
      <p className="text-ui text-ink-muted">
        Applies to the preview and to exports. Save the current settings as your own
        template to reuse them on another CV.
      </p>

      {templates.isLoading && <p className="text-ui text-ink-muted">Loading templates…</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {templates.data?.templates.map((template) => {
          const { heading, body } = faces(template);
          const active = appliedId === template.id;

          return (
            <button
              key={template.id}
              type="button"
              disabled={apply.isPending}
              onClick={() => apply.mutate(template.id)}
              className={`card p-3.5 text-left transition-colors disabled:opacity-60 ${
                active ? 'border-accent-500 ring-[3px] ring-accent-500/12' : 'hover:border-line-strong'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-ui font-semibold">{template.name}</span>
                {active && <span className="chip">Applied</span>}
              </div>
              <p className="text-meta text-ink-subtle mb-2.5">{template.description}</p>
              <div className="flex flex-col gap-0.5 font-mono text-micro text-ink-faint">
                <span>Headings · {heading}</span>
                <span>Body · {body}</span>
              </div>
            </button>
          );
        })}
      </div>

      <section className="flex flex-col gap-2">
        <span className="rail-label">Adjust</span>
        <p className="text-meta text-ink-subtle">
          Change any of this CV&rsquo;s type directly. A template is a starting point —
          these settings are what the preview and the exports actually use.
        </p>
        <TypographyEditor cvId={cvId} />
      </section>

      <section className="card p-4 flex flex-col gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="rail-label">Save as template</span>
          <p className="text-meta text-ink-subtle">
            Captures this CV&rsquo;s current typography under a name you choose, so it can
            be applied to any other CV.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Name" required>
            {(id) => (
              <TextInput
                id={id}
                value={name}
                placeholder="e.g. Exec one-pager"
                onChange={(e) => setName(e.target.value)}
              />
            )}
          </Field>
          <Field label="Description">
            {(id) => (
              <TextInput
                id={id}
                value={description}
                placeholder="Optional"
                onChange={(e) => setDescription(e.target.value)}
              />
            )}
          </Field>
        </div>
        <div className="flex items-center">
          <div className="flex-1" />
          <button
            type="button"
            className="btn btn-primary"
            disabled={!name.trim() || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? 'Saving…' : 'Save template'}
          </button>
        </div>
      </section>
    </div>
  );
}
