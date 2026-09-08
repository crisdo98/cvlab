'use client';

import { useRef } from 'react';
import {
  AddButton,
  AutoGrowTextArea,
  Field,
  IconButton,
  TextArea,
  TextInput,
} from '@/components/ui/Field';
import { MarkdownToolbar } from './MarkdownToolbar';
import type { EditorProps } from './types';
import type {
  FreeTextSectionContent,
  ListSectionContent,
  PersonalInfoContent,
} from '@/types/cv';

/* ------------------------------------------------------------- Personal */

export function PersonalInfoEditor({ form }: EditorProps<PersonalInfoContent>) {
  const { content, update } = form;
  const set = (patch: Partial<PersonalInfoContent>) =>
    update((draft) => ({ ...draft, ...patch }));

  const emailInvalid =
    content.email.length > 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(content.email);

  return (
    <div className="card p-4 flex flex-col gap-3">
      <Field
        label="CV title"
        hint="Names this CV in your list. Falls back to your name when empty."
      >
        {(id) => (
          <TextInput
            id={id}
            value={content.cv_title ?? ''}
            placeholder="e.g. Executive CV"
            onChange={(e) => set({ cv_title: e.target.value })}
          />
        )}
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Full name" required>
          {(id) => (
            <TextInput
              id={id}
              value={content.full_name}
              onChange={(e) => set({ full_name: e.target.value })}
            />
          )}
        </Field>
        <Field label="Professional title">
          {(id) => (
            <TextInput
              id={id}
              value={content.title ?? ''}
              placeholder="e.g. Head of Data Engineering"
              onChange={(e) => set({ title: e.target.value })}
            />
          )}
        </Field>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field
          label="Email"
          required
          error={emailInvalid ? 'That does not look like an email address' : undefined}
        >
          {(id) => (
            <TextInput
              id={id}
              type="email"
              value={content.email}
              onChange={(e) => set({ email: e.target.value })}
            />
          )}
        </Field>
        <Field label="Phone">
          {(id) => (
            <TextInput
              id={id}
              value={content.phone ?? ''}
              onChange={(e) => set({ phone: e.target.value })}
            />
          )}
        </Field>
      </div>

      <Field label="Location">
        {(id) => (
          <TextInput
            id={id}
            value={content.location ?? ''}
            onChange={(e) => set({ location: e.target.value })}
          />
        )}
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="LinkedIn">
          {(id) => (
            <TextInput
              id={id}
              value={content.linkedin ?? ''}
              onChange={(e) => set({ linkedin: e.target.value })}
            />
          )}
        </Field>
        <Field label="Website">
          {(id) => (
            <TextInput
              id={id}
              value={content.website ?? ''}
              onChange={(e) => set({ website: e.target.value })}
            />
          )}
        </Field>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ Free text */

export function FreeTextEditor({
  form,
  placeholder,
  hint,
}: EditorProps<FreeTextSectionContent> & { placeholder?: string; hint?: string }) {
  const { content, update } = form;
  const words = content.text.trim() ? content.text.trim().split(/\s+/).length : 0;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const setText = (text: string) => update((draft) => ({ ...draft, text }));

  return (
    <div className="card p-4 flex flex-col gap-1.5">
      <MarkdownToolbar
        textareaRef={textareaRef}
        value={content.text}
        onChange={setText}
      />
      <TextArea
        ref={textareaRef}
        rows={12}
        value={content.text}
        placeholder={placeholder ?? 'Write this section…'}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex items-center gap-2">
        <span className="font-mono text-micro text-ink-subtle">{words} words</span>
        {hint && <span className="text-meta text-ink-subtle">· {hint}</span>}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- List */

export function ListEditor({
  form,
  hint,
}: EditorProps<ListSectionContent> & { hint?: string }) {
  const { content, update } = form;

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        {content.items.length === 0 && (
          <p className="text-ui text-ink-muted">Nothing here yet.</p>
        )}
        {content.items.map((item, index) => (
          <div key={index} className="flex items-start gap-2">
            <AutoGrowTextArea
              value={item.text}
              placeholder="e.g. Python, AWS, Terraform"
              onChange={(e) =>
                update((draft) => ({
                  ...draft,
                  items: draft.items.map((it, i) =>
                    i === index ? { ...it, text: e.target.value } : it
                  ),
                }))
              }
            />
            <IconButton
              label="Remove item"
              tone="danger"
              className="mt-1"
              onClick={() =>
                update((draft) => ({
                  ...draft,
                  items: draft.items.filter((_, i) => i !== index),
                }))
              }
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </IconButton>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <AddButton
          onClick={() =>
            update((draft) => ({ ...draft, items: [...draft.items, { text: '' }] }))
          }
        >
          Add item
        </AddButton>
        {hint && <span className="text-meta text-ink-subtle">{hint}</span>}
      </div>
    </div>
  );
}
