'use client';

import { useRef, type RefObject } from 'react';

/**
 * A small formatting bar for the Markdown-backed text areas.
 *
 * CV text is stored and exported as Markdown, but nothing in the editor said
 * so — people typed `**bold**` only if they already knew the syntax. These
 * buttons wrap the selection, or insert a marker at the cursor, and put focus
 * back where it was so typing can continue uninterrupted.
 */

interface Action {
  label: string;
  title: string;
  /** Text placed either side of the selection. */
  wrap?: [string, string];
  /** Marker placed at the start of each selected line. */
  linePrefix?: string;
  className?: string;
}

const ACTIONS: Action[] = [
  { label: 'B', title: 'Bold', wrap: ['**', '**'], className: 'font-bold' },
  { label: 'I', title: 'Italic', wrap: ['*', '*'], className: 'italic' },
  { label: '• List', title: 'Bullet list', linePrefix: '- ' },
  { label: '1. List', title: 'Numbered list', linePrefix: '1. ' },
];

export function MarkdownToolbar({
  textareaRef,
  value,
  onChange,
}: {
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (next: string) => void;
}) {
  const busy = useRef(false);

  const apply = (action: Action) => {
    const field = textareaRef.current;
    if (!field || busy.current) return;
    busy.current = true;

    const start = field.selectionStart ?? 0;
    const end = field.selectionEnd ?? 0;
    const selected = value.slice(start, end);

    let next: string;
    let caret: [number, number];

    if (action.linePrefix) {
      // Work on whole lines, so a marker never lands mid-sentence.
      const lineStart = value.lastIndexOf('\n', start - 1) + 1;
      const lineEnd = end === start ? value.indexOf('\n', end) : end;
      const stop = lineEnd === -1 ? value.length : lineEnd;
      const block = value.slice(lineStart, stop) || '';

      const lines = block.split('\n');
      const already = lines.every((line) => line.startsWith(action.linePrefix!));
      const rewritten = lines
        .map((line, i) => {
          if (already) return line.slice(action.linePrefix!.length);
          const prefix =
            action.linePrefix === '1. ' ? `${i + 1}. ` : action.linePrefix!;
          return `${prefix}${line}`;
        })
        .join('\n');

      next = value.slice(0, lineStart) + rewritten + value.slice(stop);
      caret = [lineStart, lineStart + rewritten.length];
    } else {
      const [open, close] = action.wrap!;
      // Toggle off when the selection is already wrapped.
      const wrapped =
        selected.startsWith(open) && selected.endsWith(close) && selected.length > open.length + close.length;
      const body = wrapped ? selected.slice(open.length, selected.length - close.length) : `${open}${selected}${close}`;
      next = value.slice(0, start) + body + value.slice(end);
      caret = selected ? [start, start + body.length] : [start + open.length, start + open.length];
    }

    onChange(next);
    requestAnimationFrame(() => {
      field.focus();
      field.setSelectionRange(caret[0], caret[1]);
      busy.current = false;
    });
  };

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {ACTIONS.map((action) => (
        <button
          key={action.label}
          type="button"
          title={action.title}
          aria-label={action.title}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => apply(action)}
          className={`h-6 px-2 rounded-[3px] text-meta text-ink-muted hover:bg-line-soft hover:text-ink transition-colors ${action.className ?? ''}`}
        >
          {action.label}
        </button>
      ))}
      <span className="text-meta text-ink-faint ml-1">
        Markdown · a blank line starts a new paragraph
      </span>
    </div>
  );
}
