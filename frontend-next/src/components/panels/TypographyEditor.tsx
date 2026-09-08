'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { typographyApi } from '@/lib/api';
import { cvKeys } from '@/hooks/useCVs';
import { toast } from '@/lib/toast';
import { friendlyMessage } from '@/lib/errors';
import { Field, TextInput } from '@/components/ui/Field';

/** Matches FontFamily on the backend; the exporter maps these to real faces. */
const FONTS = [
  'Liberation Sans',
  'Liberation Serif',
  'Times New Roman',
  'Arial',
  'Helvetica',
  'Georgia',
  'Palatino',
  'Courier',
];

const WEIGHTS = ['normal', 'bold', 'light'];

/**
 * Bullet characters offered for lists.
 *
 * Every one of these maps to a LaTeX symbol the exporter can draw. A template
 * shipped "▸", which Liberation Sans does not contain — so exported CVs had an
 * empty box on every line and no way to change it from the app.
 */
const BULLETS = [
  { value: '•', label: '•  Round' },
  { value: '◦', label: '◦  Hollow' },
  { value: '▪', label: '▪  Square' },
  { value: '▸', label: '▸  Triangle' },
  { value: '–', label: '–  Dash' },
];
const ALIGNMENTS = ['left', 'center', 'right', 'justify'];

/** The styles a CV exposes, in the order they appear on the page. */
const STYLES: { key: string; label: string; hint: string }[] = [
  { key: 'h1_style', label: 'Name', hint: 'The heading at the top' },
  { key: 'contact_style', label: 'Contact line', hint: 'Email, phone, location' },
  { key: 'h2_style', label: 'Section headings', hint: 'Experience, Education…' },
  { key: 'h3_style', label: 'Entry headings', hint: 'Job and qualification titles' },
  { key: 'body_style', label: 'Body text', hint: 'Descriptions and bullets' },
];

interface Colour {
  r: number;
  g: number;
  b: number;
}

interface TextStyle {
  font_family?: string;
  font_size?: number;
  font_weight?: string;
  font_style?: string;
  color?: Colour;
  line_height?: number;
  alignment?: string;
}

type Config = Record<string, unknown>;

function hexOf(colour: Colour | undefined): string {
  const { r = 0, g = 0, b = 0 } = colour ?? {};
  return `#${[r, g, b].map((c) => Math.max(0, Math.min(255, c)).toString(16).padStart(2, '0')).join('')}`;
}

function rgbOf(hex: string): Colour {
  const value = hex.replace('#', '');
  return {
    r: parseInt(value.slice(0, 2), 16) || 0,
    g: parseInt(value.slice(2, 4), 16) || 0,
    b: parseInt(value.slice(4, 6), 16) || 0,
  };
}

function Select({
  id,
  value,
  options,
  onChange,
}: {
  id?: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  );
}

/**
 * Edit a CV's typography directly.
 *
 * Applying or duplicating a template got you someone else's settings; there was
 * no way to change them afterwards, which made a duplicated template pointless.
 * This edits the same stored config the preview and the exporter both read, so
 * a change here shows up in both.
 */
export function TypographyEditor({ cvId }: { cvId: string }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Config | null>(null);
  // Set from the server response, so "has anything changed" is a comparison
  // against what is actually stored rather than against the last save.
  const [saved, setSaved] = useState<string | null>(null);
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);

  const stored = useQuery({
    queryKey: ['typography', cvId],
    queryFn: () => typographyApi.forCV(cvId),
  });

  useEffect(() => {
    if (!stored.data) return;
    const payload = stored.data as { typography?: Config };
    const config = payload.typography ?? (stored.data as Config);
    setDraft(structuredClone(config));
    setSaved(JSON.stringify(config));
    setConfirmingDiscard(false);
  }, [stored.data]);

  const save = useMutation({
    mutationFn: () => typographyApi.updateForCV(cvId, draft as Config),
    onSuccess: () => {
      // The preview reads typography off the CV, so both caches must refresh.
      queryClient.invalidateQueries({ queryKey: cvKeys.detail(cvId) });
      queryClient.invalidateQueries({ queryKey: ['typography', cvId] });
      setSaved(JSON.stringify(draft));
      toast.success('Styling updated');
    },
    onError: (error) => toast.error(friendlyMessage(error, 'Could not save the styling')),
  });

  if (stored.isLoading) return <p className="text-ui text-ink-muted">Loading styling…</p>;
  if (!draft) return null;

  const dirty = saved !== null && JSON.stringify(draft) !== saved;

  const styleOf = (key: string): TextStyle => (draft[key] as TextStyle) ?? {};

  const setStyle = (key: string, patch: Partial<TextStyle>) =>
    setDraft((current) => ({
      ...(current ?? {}),
      [key]: { ...((current?.[key] as TextStyle) ?? {}), ...patch },
    }));

  const margins = (draft.page_margins as Record<string, number>) ?? {};
  const setMargin = (edge: string, value: number) =>
    setDraft((current) => ({
      ...(current ?? {}),
      page_margins: { ...((current?.page_margins as Record<string, number>) ?? {}), [edge]: value },
    }));

  const setSpacing = (key: string, value: number | string) =>
    setDraft((current) => ({ ...(current ?? {}), [key]: value }));

  return (
    <div className="flex flex-col gap-4">
      {STYLES.map(({ key, label, hint }) => {
        const style = styleOf(key);
        return (
          <section key={key} className="card p-4 flex flex-col gap-3">
            <div className="flex flex-col gap-0.5">
              <span className="text-ui font-semibold">{label}</span>
              <span className="text-meta text-ink-subtle">{hint}</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Field label="Font">
                {(id) => (
                  <Select
                    id={id}
                    value={style.font_family ?? FONTS[0]}
                    options={FONTS}
                    onChange={(value) => setStyle(key, { font_family: value })}
                  />
                )}
              </Field>
              <Field label="Size (pt)">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    min="6"
                    max="72"
                    value={style.font_size ?? 11}
                    onChange={(e) => setStyle(key, { font_size: Number(e.target.value) })}
                  />
                )}
              </Field>
              <Field label="Weight">
                {(id) => (
                  <Select
                    id={id}
                    value={style.font_weight ?? 'normal'}
                    options={WEIGHTS}
                    onChange={(value) => setStyle(key, { font_weight: value })}
                  />
                )}
              </Field>
              <Field label="Alignment">
                {(id) => (
                  <Select
                    id={id}
                    value={style.alignment ?? 'left'}
                    options={ALIGNMENTS}
                    onChange={(value) => setStyle(key, { alignment: value })}
                  />
                )}
              </Field>
              <Field label="Line height">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    step="0.05"
                    min="0.8"
                    max="3"
                    value={style.line_height ?? 1.5}
                    onChange={(e) => setStyle(key, { line_height: Number(e.target.value) })}
                  />
                )}
              </Field>
              <Field label="Colour">
                {(id) => (
                  <input
                    id={id}
                    type="color"
                    className="input h-8 p-1 cursor-pointer"
                    value={hexOf(style.color)}
                    onChange={(e) => setStyle(key, { color: rgbOf(e.target.value) })}
                  />
                )}
              </Field>
            </div>
          </section>
        );
      })}

      <section className="card p-4 flex flex-col gap-3">
        <span className="text-ui font-semibold">Page</span>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {(['top', 'right', 'bottom', 'left'] as const).map((edge) => (
            <Field key={edge} label={`${edge[0].toUpperCase()}${edge.slice(1)} margin (in)`}>
              {(id) => (
                <TextInput
                  id={id}
                  type="number"
                  step="0.05"
                  min="0.2"
                  max="2"
                  value={margins[edge] ?? 0.75}
                  onChange={(e) => setMargin(edge, Number(e.target.value))}
                />
              )}
            </Field>
          ))}
          <Field label="Bullet">
            {(id) => (
              <select
                id={id}
                className="input"
                value={(draft.bullet_style as string) ?? '•'}
                onChange={(e) => setSpacing('bullet_style', e.target.value)}
              >
                {BULLETS.map((bullet) => (
                  <option key={bullet.value} value={bullet.value}>
                    {bullet.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Paragraph spacing (pt)">
            {(id) => (
              <TextInput
                id={id}
                type="number"
                step="1"
                min="0"
                max="40"
                value={(draft.paragraph_spacing as number) ?? 6}
                onChange={(e) => setSpacing('paragraph_spacing', Number(e.target.value))}
              />
            )}
          </Field>
          <Field label="Section spacing (pt)">
            {(id) => (
              <TextInput
                id={id}
                type="number"
                step="1"
                min="0"
                max="40"
                value={(draft.section_spacing as number) ?? 8}
                onChange={(e) => setSpacing('section_spacing', Number(e.target.value))}
              />
            )}
          </Field>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-meta text-ink-subtle">
          {dirty
            ? 'Unsaved changes — the preview and exports still use the saved styling.'
            : 'Changes apply to the preview and to exports once saved.'}
        </span>
        <div className="flex-1" />

        {confirmingDiscard ? (
          <span className="flex items-center gap-1.5">
            <span className="text-meta text-ink-muted">Discard your changes?</span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setConfirmingDiscard(false)}
            >
              Keep editing
            </button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => {
                setConfirmingDiscard(false);
                stored.refetch();
              }}
            >
              Discard
            </button>
          </span>
        ) : (
          <button
            type="button"
            className="btn btn-secondary"
            // Nothing to discard when the draft matches what is stored, so the
            // button stays out of the way until it would actually do something.
            disabled={save.isPending || !dirty}
            onClick={() => setConfirmingDiscard(true)}
          >
            Discard
          </button>
        )}

        <button
          type="button"
          className="btn btn-primary"
          disabled={save.isPending || !dirty}
          onClick={() => save.mutate()}
        >
          {save.isPending ? 'Saving…' : 'Save styling'}
        </button>
      </div>
    </div>
  );
}
