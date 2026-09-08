import type { ReactNode } from 'react';

/**
 * A deliberately small Markdown renderer for CV free text.
 *
 * Descriptions are authored as Markdown, and the exports run through pandoc,
 * so the preview showing raw `**bold**` was a straight mismatch with the PDF.
 * This covers what CV text actually uses — bold, italic, inline code, links,
 * bullet and numbered lists, and line breaks — and nothing else.
 *
 * It builds React nodes rather than HTML strings, so CV content can never be
 * injected as markup no matter what a user types or an import produces.
 */

const LIST_ITEM = /^\s{0,3}(?:[-*+]\s+|\d+[.)]\s+)(.*)$/;

/** Split a line into bold/italic/code/link runs. */
export function renderInline(text: string, keyPrefix = ''): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Ordered so ** is matched before *, and escaped markers are left alone.
  const pattern =
    /(\*\*|__)(?=\S)([\s\S]*?\S)\1|(\*|_)(?=\S)([\s\S]*?\S)\3|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;

  let last = 0;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const key = `${keyPrefix}i${index++}`;

    if (match[2] !== undefined) {
      nodes.push(
        <strong key={key} style={{ fontWeight: 700 }}>
          {renderInline(match[2], `${key}-`)}
        </strong>
      );
    } else if (match[4] !== undefined) {
      nodes.push(
        <em key={key} style={{ fontStyle: 'italic' }}>
          {renderInline(match[4], `${key}-`)}
        </em>
      );
    } else if (match[5] !== undefined) {
      nodes.push(
        <code key={key} style={{ fontFamily: 'monospace' }}>
          {match[5]}
        </code>
      );
    } else if (match[6] !== undefined) {
      // Rendered as plain text: a CV preview is a document, not a browser.
      nodes.push(<span key={key}>{match[6]}</span>);
    }
    last = pattern.lastIndex;
  }

  if (last < text.length) nodes.push(text.slice(last));
  return nodes.length ? nodes : [text];
}

interface ParagraphBlock {
  type: 'paragraph';
  lines: string[];
}
interface ListBlock {
  type: 'list';
  items: string[];
  ordered: boolean;
}
export type MarkdownBlock = ParagraphBlock | ListBlock;

/**
 * Group lines into paragraphs and lists.
 *
 * A list is recognised whether or not a blank line precedes it. Markdown
 * proper would fold an unseparated list into the paragraph above, but CV text
 * is written in a textarea where people do not leave blank lines, and the
 * exporter now inserts that separation itself.
 */
export function parseBlocks(text: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const lines = text.replace(/\r\n?/g, '\n').split('\n');

  // A blank line ends the current block. Skipping it merged consecutive
  // paragraphs into one, so pressing Enter twice showed as a single line break
  // in the preview while the export correctly produced two paragraphs.
  let broken = false;

  for (const raw of lines) {
    // A trailing backslash is pandoc's hard break; it is structure, not text.
    const line = raw.replace(/\\$/, '').trim();
    if (!line) {
      broken = true;
      continue;
    }

    const item = LIST_ITEM.exec(line);
    if (item) {
      const ordered = /^\s{0,3}\d/.test(line);
      const previous = blocks[blocks.length - 1];
      if (!broken && previous?.type === 'list' && previous.ordered === ordered) {
        previous.items.push(item[1]);
      } else {
        blocks.push({ type: 'list', items: [item[1]], ordered });
      }
      broken = false;
      continue;
    }

    const previous = blocks[blocks.length - 1];
    if (!broken && previous?.type === 'paragraph') {
      previous.lines.push(line);
    } else {
      blocks.push({ type: 'paragraph', lines: [line] });
    }
    broken = false;
  }

  return blocks;
}

/** Render CV free text as document nodes. */
export function Markdown({
  text,
  bulletColor,
}: {
  text: string;
  bulletColor?: string;
}): ReactNode {
  const blocks = parseBlocks(text);
  if (!blocks.length) return null;

  return (
    <>
      {blocks.map((block, blockIndex) =>
        block.type === 'list' ? (
          <ul key={blockIndex} className="flex flex-col" style={{ gap: 'calc(var(--md-gap, 6px) * 0.5)', margin: 'var(--md-gap, 6px) 0' }}>
            {block.items.map((item, i) => (
              <li key={i} className="flex gap-2.5">
                <span style={{ color: bulletColor }}>{block.ordered ? `${i + 1}.` : '•'}</span>
                <span>{renderInline(item, `${blockIndex}-${i}-`)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p key={blockIndex} style={{ marginBottom: 'var(--md-gap, 6px)' }}>
            {block.lines.map((line, i) => (
              <span key={i}>
                {renderInline(line, `${blockIndex}-${i}-`)}
                {i < block.lines.length - 1 && <br />}
              </span>
            ))}
          </p>
        )
      )}
    </>
  );
}
