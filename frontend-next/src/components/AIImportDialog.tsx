'use client';

import { useState } from 'react';
import { aiImportApi, type AIParsingResult } from '@/lib/api';
import { friendlyMessage } from '@/lib/errors';

/**
 * Encode bytes as base64 without spreading the whole buffer into apply(),
 * which throws on large files.
 */
function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const chunk = 0x8000;
  let binary = '';
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function Spinner({ className = 'w-3.5 h-3.5' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

/**
 * Import a CV by reading it with the LLM.
 *
 * Unlike the Markdown importer, which parses a known layout deterministically,
 * this asks the model to identify sections and extract entities. That suits
 * documents the Markdown parser cannot read — a CV pasted from a PDF, or one
 * with an unusual structure — and is less reliable on a well-formed .md, where
 * the deterministic importer is the better tool.
 *
 * Because the quality varies, the parse is shown for review before anything is
 * created rather than silently producing a CV.
 */
export function AIImportDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (cvId: string) => void;
}) {
  const [text, setText] = useState('');
  const [filename, setFilename] = useState<string | null>(null);
  // PDF and DOCX reach the backend as base64, which extracts the text there.
  // Only their format and size are shown, since the payload is not readable.
  const [binary, setBinary] = useState<{ format: string; size: number } | null>(null);
  const [result, setResult] = useState<AIParsingResult | null>(null);
  const [busy, setBusy] = useState<'parsing' | 'creating' | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const reset = () => {
    setText('');
    setFilename(null);
    setBinary(null);
    setResult(null);
    setError(null);
    setBusy(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  /** Formats the backend extracts from bytes rather than reading as text. */
  const BINARY_FORMATS = ['pdf', 'docx', 'doc'];

  const readFile = async (file: File | undefined) => {
    if (!file) return;
    setResult(null);
    setError(null);
    setFilename(file.name);

    const format = file.name.split('.').pop()?.toLowerCase() ?? '';

    if (BINARY_FORMATS.includes(format)) {
      // A PDF read as text is mojibake, so the bytes are sent instead and the
      // backend extracts them with PyPDF2 / python-docx.
      const buffer = await file.arrayBuffer();
      setText(toBase64(buffer));
      setBinary({ format, size: file.size });
      return;
    }

    setText(await file.text());
    setBinary(null);
  };

  const parse = async () => {
    setBusy('parsing');
    setError(null);
    try {
      const format = filename?.split('.').pop()?.toLowerCase() || 'txt';
      setResult(await aiImportApi.parse(text, format, filename ?? undefined));
    } catch (err) {
      setError(friendlyMessage(err, 'Could not read that document'));
    } finally {
      setBusy(null);
    }
  };

  const create = async () => {
    if (!result?.cv_data) return;
    setBusy('creating');
    try {
      const response = await aiImportApi.createFromParsed(result.cv_data);
      const cv = (response as { cv?: { id: string } }).cv ?? (response as unknown as { id: string });
      onCreated(cv.id);
      reset();
    } catch (err) {
      setError(friendlyMessage(err, 'Could not create the CV'));
      setBusy(null);
    }
  };

  const confidence = result ? Math.round(result.overall_confidence * 100) : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="card w-full max-w-2xl max-h-[85vh] flex flex-col p-5 gap-4 overflow-auto">
        <header className="flex items-start gap-3">
          <div className="flex flex-col gap-0.5 flex-1 min-w-0">
            <h2 className="text-lg font-semibold tracking-[-0.01em]">Import with AI</h2>
            <p className="text-meta text-ink-muted">
              Reads a PDF, Word document, or pasted text. For a well-formed Markdown
              CV, plain Import Markdown is more accurate.
            </p>
          </div>
          <button type="button" className="btn btn-secondary" onClick={close}>
            Close
          </button>
        </header>

        <label className="btn btn-secondary self-start cursor-pointer">
          <input
            type="file"
            accept=".md,.markdown,.txt,.html,.pdf,.docx"
            className="hidden"
            onChange={(e) => void readFile(e.target.files?.[0])}
          />
          {filename ? `File: ${filename}` : 'Choose a file'}
        </label>

        {binary ? (
          <div className="card p-3 flex items-center gap-3">
            <span className="chip flex-shrink-0">{binary.format}</span>
            <span className="flex-1 min-w-0 text-ui truncate">{filename}</span>
            <span className="font-mono text-micro text-ink-faint">
              {(binary.size / 1024).toFixed(0)} KB
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setBinary(null);
                setText('');
                setFilename(null);
                setResult(null);
              }}
            >
              Clear
            </button>
          </div>
        ) : (
          <textarea
            className="input min-h-40 font-mono text-[12px]"
            placeholder="…or paste the CV text here"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setResult(null);
            }}
          />
        )}
        {binary && (
          <p className="text-meta text-ink-subtle">
            The text is extracted from this file on the server, so nothing is readable
            here until it has been read.
          </p>
        )}

        {error && <div className="alert alert-warning mb-0">{error}</div>}

        {result && (
          <section className="flex flex-col gap-2">
            <div className="flex items-baseline gap-2">
              <span className="rail-label">Parsed</span>
              <span className="font-mono text-micro text-ink-subtle">
                {confidence}% confidence
              </span>
            </div>
            <ul className="card divide-y divide-line">
              {result.parsed_sections.map((section, i) => (
                <li key={i} className="flex items-center gap-3 px-3 h-9">
                  <span className="chip flex-shrink-0">{section.section_type}</span>
                  <span className="flex-1 min-w-0 text-meta text-ink-muted truncate">
                    {section.content && Object.keys(section.content).length
                      ? Object.keys(section.content).join(', ')
                      : 'nothing extracted'}
                  </span>
                  <span className="font-mono text-micro text-ink-faint">
                    {Math.round(section.confidence * 100)}%
                  </span>
                </li>
              ))}
            </ul>
            {!result.cv_data && (
              <div className="alert alert-warning mb-0">
                {result.errors[0] ??
                  'Confidence was too low to build a CV from this. Try the Markdown importer.'}
              </div>
            )}
          </section>
        )}

        <div className="flex items-center gap-2">
          <div className="flex-1" />
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!text.trim() || busy !== null}
            onClick={() => void parse()}
          >
            {busy === 'parsing' ? <Spinner /> : null}
            {busy === 'parsing' ? 'Reading…' : result ? 'Read again' : 'Read document'}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!result?.cv_data || busy !== null}
            onClick={() => void create()}
          >
            {busy === 'creating' ? <Spinner /> : null}
            {busy === 'creating' ? 'Creating…' : 'Create CV'}
          </button>
        </div>
      </div>
    </div>
  );
}
