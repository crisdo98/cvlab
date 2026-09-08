'use client';

import { useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import type {
  CertificationEntry,
  EducationEntry,
  ExperienceEntry,
  Section,
} from '@/types/cv';
import { Markdown, renderInline } from '@/lib/markdown';
import {
  PAGE_HEIGHT,
  PAGE_WIDTH,
  resolveTypography,
  type ResolvedTypography,
} from '@/lib/typography';

/**
 * A unit of content that must not be split across a page break: a section
 * heading with its first entry, or one entry on its own. Pagination packs
 * these into pages by measured height, which is the only reliable way to know
 * where a page ends when text reflows.
 */
interface Block {
  key: string;
  node: ReactNode;
  /** Heading blocks must never be the last thing on a page. */
  isHeading?: boolean;
  /**
   * Space this block asks for above itself, in px. Carried on the wrapper
   * rather than inside the node so it can be dropped at the top of a page,
   * where a leading margin would otherwise leave a gap the export does not
   * have.
   */
  lead?: number;
}

/**
 * The identifying part of an entry: its title, employer, dates and any
 * description. Achievements are separate blocks so a long list can flow across
 * a page break, which is what the PDF does. Keeping a whole job together made
 * an entry with eleven bullets taller than the space left on the page, so the
 * entire section jumped to the next one.
 */
function EntryHead({
  entry,
  type,
}: {
  entry: ExperienceEntry & EducationEntry & CertificationEntry;
  type: ResolvedTypography;
}) {
  const heading = entry.title || entry.degree || entry.name || '';
  const org = entry.company || entry.institution || entry.issuer || '';
  const dates = [entry.start_date || entry.date, entry.current ? 'Present' : entry.end_date]
    .filter(Boolean)
    .join(' – ');

  return (
    <div>
      <div className="flex items-baseline gap-2 mb-0.5" style={type.h3}>
        <span>{heading}</span>
        {org && <span style={{ opacity: 0.5 }}>—</span>}
        {org && <span style={{ fontWeight: 'normal' }}>{org}</span>}
      </div>
      {(entry.location || dates) && (
        <div className="mb-2" style={{ ...type.contact, fontStyle: 'italic' }}>
          {[entry.location, dates].filter(Boolean).join(' | ')}
        </div>
      )}
      {entry.description && (
        <div style={{ ...type.body, marginBottom: type.paragraphSpacing, ['--md-gap' as string]: `${type.paragraphSpacing}px` }}>
          <Markdown text={entry.description} bulletColor={type.h2.color as string} />
        </div>
      )}
    </div>
  );
}

/** One achievement, laid out to match the others so a split is invisible. */
function AchievementRow({ text, type }: { text: string; type: ResolvedTypography }) {
  return (
    <div className="flex gap-2.5 pl-0.5" style={{ ...type.body, marginBottom: 6 }}>
      <span style={{ color: type.h2.color }}>{type.bullet}</span>
      <span>{renderInline(text)}</span>
    </div>
  );
}

/**
 * Wrapper for one block, used identically in the measuring pass and on the
 * page. `flow-root` stops the child's margins collapsing out of the box, so a
 * measured height is the height the block actually occupies.
 */
const BLOCK_WRAPPER: CSSProperties = { display: 'flow-root' };

/** Sections shown as a comma-separated run rather than a bullet per item. */
const COMMA_SEPARATED_SECTIONS = new Set(['skills']);

/**
 * Flatten the CV into page-breakable blocks.
 *
 * Sections are split at entry level rather than kept whole, so a long
 * experience section flows across pages instead of overflowing one.
 */
function buildBlocks(
  visible: Section[],
  name: string,
  role: string | null,
  contact: string[],
  type: ResolvedTypography
): Block[] {
  const blocks: Block[] = [];

  blocks.push({
    key: 'header',
    node: (
      <div className="mb-5">
        <div className="mb-1.5" style={type.h1}>
          {name}
        </div>
        {role && (
          <div className="mb-3.5" style={{ ...type.h2, letterSpacing: '0.02em' }}>
            {role}
          </div>
        )}
        {contact.length > 0 && (
          <div className="mb-5" style={type.contact}>
            {contact.join(' · ')}
          </div>
        )}
        <div className="h-0.5" style={{ backgroundColor: type.h2.color }} />
      </div>
    ),
  });

  for (const section of visible.filter((s) => s.type !== 'personal_info')) {
    const headingNode = (
      <h2
        className="uppercase"
        style={{
          ...type.h2,
          letterSpacing: '0.14em',
          fontSize: `calc(${type.h2.fontSize} * 0.72)`,
          marginBottom: type.paragraphSpacing,
        }}
      >
        {section.title}
      </h2>
    );

    const content = section.content;
    const children: ReactNode[] = [];

    // Break the section into the smallest pieces that can stand alone. Coarse
    // pieces cannot flow across a page the way the PDF does: a job with eleven
    // bullets was one block, too tall for the space left, so the whole section
    // moved to the next page and left half a page empty.
    if (content.content_type === 'free_text') {
      // One piece per paragraph, so a long summary flows rather than jumping.
      const paragraphs = content.text
        .split(/\n\s*\n/)
        .map((part) => part.trim())
        .filter(Boolean);
      const pieces = paragraphs.length ? paragraphs : [content.text];
      pieces.forEach((paragraph, i) => {
        children.push(
          <div
            key={`text-${i}`}
            style={{
              ...type.body,
              marginBottom: type.paragraphSpacing,
              ['--md-gap' as string]: `${type.paragraphSpacing}px`,
            }}
          >
            <Markdown text={paragraph} bulletColor={type.h2.color as string} />
          </div>
        );
      });
    } else if (content.content_type === 'list') {
      // Skills read as a run of comma-separated terms, matching the export.
      // One bullet per skill turns twenty of them into most of a page.
      if (COMMA_SEPARATED_SECTIONS.has(section.type)) {
        const joined = content.items
          .map((item) => item.text)
          .filter(Boolean)
          .join(', ');
        if (joined) {
          children.push(
            <div key="skills" style={{ ...type.body, marginBottom: type.paragraphSpacing }}>
              {renderInline(joined)}
            </div>
          );
        }
      } else {
        content.items.forEach((item, i) => {
          children.push(
            <div key={`item-${i}`} className="flex gap-2.5" style={{ ...type.body, marginBottom: 6 }}>
              <span style={{ color: type.h2.color }}>{type.bullet}</span>
              <span>{renderInline(item.text)}</span>
            </div>
          );
        });
      }
    } else if (content.content_type === 'structured') {
      for (const raw of content.entries) {
        const entry = raw as ExperienceEntry & EducationEntry & CertificationEntry;
        children.push(
          <div key={entry.id}>
            <EntryHead entry={entry} type={type} />
          </div>
        );
        (entry.achievements ?? []).forEach((achievement, i) => {
          children.push(
            <AchievementRow key={`${entry.id}-a${i}`} text={achievement} type={type} />
          );
        });
        // Gap after the entry, carried by the last piece so it can be dropped
        // when that piece ends a page.
        children.push(
          <div key={`${entry.id}-gap`} style={{ height: type.paragraphSpacing }} aria-hidden="true" />
        );
      }
    }

    // The heading travels with the first child so a section never starts at
    // the very bottom of a page with its content overleaf.
    blocks.push({
      key: `${section.id}-head`,
      isHeading: true,
      lead: type.sectionSpacing * 2,
      node: (
        <div>
          {headingNode}
          {children[0]}
        </div>
      ),
    });

    children.slice(1).forEach((child, i) => {
      blocks.push({ key: `${section.id}-${i}`, node: child });
    });
  }

  return blocks;
}

/** A measured block: its own height, plus the gap it asks for above itself. */
export interface Measured {
  height: number;
  lead: number;
}

function asMeasured(item: number | Measured): Measured {
  return typeof item === 'number' ? { height: item, lead: 0 } : item;
}

/**
 * Pack blocks into pages using their measured heights. Exported for testing.
 *
 * A block's leading margin is only charged when it follows something on the
 * same page. At the top of a page that margin collapses away in any real
 * layout, and counting it made a section heading with generous spacing look
 * too tall to fit — pushing each section onto a page of its own.
 */
export function paginate(
  items: (number | Measured)[],
  contentHeight: number
): number[][] {
  if (!items.length) return [[]];
  const pages: number[][] = [];
  let current: number[] = [];
  let used = 0;

  items.forEach((item, index) => {
    const { height, lead } = asMeasured(item);
    const needed = current.length ? height + lead : height;

    // A block taller than a page cannot be helped; give it its own page and
    // let it overflow rather than looping forever.
    if (current.length && used + needed > contentHeight) {
      pages.push(current);
      current = [];
      used = 0;
    }
    current.push(index);
    used += current.length === 1 ? height : needed;
  });

  if (current.length) pages.push(current);
  return pages;
}

export function CVPreview({
  sections,
  typography,
  zoom,
  onZoom,
}: {
  sections: Section[];
  typography?: Record<string, unknown> | null;
  zoom: number;
  onZoom: (zoom: number) => void;
}) {
  const type = useMemo(() => resolveTypography(typography), [typography]);

  const visible = useMemo(
    () => sections.filter((s) => s.visible !== false).sort((a, b) => a.order - b.order),
    [sections]
  );

  const personal = visible.find((s) => s.type === 'personal_info');
  const info = personal?.content as
    | { full_name?: string; title?: string; email?: string; phone?: string; location?: string; linkedin?: string }
    | undefined;

  const contact = [info?.location, info?.phone, info?.email, info?.linkedin].filter(
    Boolean
  ) as string[];

  // A stable key for the contact line: the array is rebuilt every render, so
  // depending on it directly would rebuild every block each time.
  const contactKey = contact.join('|');

  const blocks = useMemo(
    () => buildBlocks(visible, info?.full_name || 'Your name', info?.title ?? null, contactKey.split('|').filter(Boolean), type),
    [visible, info?.full_name, info?.title, contactKey, type]
  );

  const measureRef = useRef<HTMLDivElement>(null);
  const [pages, setPages] = useState<number[][]>([]);

  // Measure off-screen at full scale, then pack. Re-runs whenever the content
  // or the typography changes, since either alters the heights.
  useLayoutEffect(() => {
    const container = measureRef.current;
    if (!container) return;

    const measure = () => {
      const node = measureRef.current;
      if (!node) return;
      const measured = Array.from(node.children).map((child) => {
        const element = child as HTMLElement;
        // Each wrapper is display:flow-root (see BLOCK_WRAPPER), so its box
        // contains the child's margins instead of letting them collapse
        // through. Measuring without that lost 6px per bullet — around 60px a
        // page, which is why a row was clipped at the page bottom.
        const rect = element.getBoundingClientRect().height;
        // The leading gap lives on the wrapper, so pagination can drop it at
        // the top of a page where the export has no such gap.
        const lead = parseFloat(window.getComputedStyle(element).marginTop || '0') || 0;
        return { height: rect, lead };
      });
      const next = paginate(measured, type.contentHeight);
      // Only replace the layout when it actually differs. Setting a fresh
      // array every measurement re-rendered the preview, which re-ran this
      // effect — a loop that kept the pagination unsettled.
      setPages((current) =>
        JSON.stringify(current) === JSON.stringify(next) ? current : next
      );
    };

    measure();

    // Text measured before the webfont arrives is the wrong height, which
    // shows up as pages breaking in the wrong place on first paint.
    let cancelled = false;
    document.fonts?.ready.then(() => {
      if (!cancelled) measure();
    });
    return () => {
      cancelled = true;
    };
  }, [blocks, type]);

  /**
   * Page layout that is always valid for the blocks currently rendered.
   *
   * `pages` is measured in an effect, so for one render after the content
   * changes it still holds the previous indices. Hiding a section shrank
   * `blocks` first, and reading blocks[index].key off the end threw — which is
   * why hiding a section showed "This page couldn't load" until a reload.
   */
  const laidOut = useMemo(() => {
    const valid = pages
      .map((page) => page.filter((index) => index < blocks.length))
      .filter((page) => page.length > 0);
    if (valid.length) return valid;
    // Before the first measurement, show everything on one page rather than
    // nothing.
    return blocks.length ? [blocks.map((_, index) => index)] : [];
  }, [pages, blocks]);

  const scale = zoom / 100;
  const pageStyle: CSSProperties = {
    width: PAGE_WIDTH,
    height: PAGE_HEIGHT,
    padding: type.padding,
    backgroundColor: '#ffffff',
    overflow: 'hidden',
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="h-9 flex-shrink-0 flex items-center gap-1 px-3 border-b border-line">
        <span className="rail-label">Preview</span>
        {laidOut.length > 0 && (
          <span className="meta-mono text-ink-subtle">
            {laidOut.length} page{laidOut.length === 1 ? '' : 's'}
          </span>
        )}
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => onZoom(Math.max(30, zoom - 5))}
          disabled={zoom <= 30}
          className="w-6 h-6 flex items-center justify-center rounded-[3px] text-ink-muted hover:bg-line-soft disabled:opacity-40"
          aria-label="Zoom out"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 12h14" />
          </svg>
        </button>
        <span className="meta-mono w-9 text-center">{zoom}%</span>
        <button
          type="button"
          onClick={() => onZoom(Math.min(150, zoom + 5))}
          disabled={zoom >= 150}
          className="w-6 h-6 flex items-center justify-center rounded-[3px] text-ink-muted hover:bg-line-soft disabled:opacity-40"
          aria-label="Zoom in"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-auto bg-ground-sunken p-4">
        {/* Off-screen measurement pass: same width and styles as a real page. */}
        <div
          ref={measureRef}
          aria-hidden="true"
          style={{
            position: 'absolute',
            visibility: 'hidden',
            pointerEvents: 'none',
            top: 0,
            left: -99999,
            width: type.contentWidth,
          }}
        >
          {blocks.map((block) => (
            <div key={block.key} style={{ ...BLOCK_WRAPPER, marginTop: block.lead }}>
              {block.node}
            </div>
          ))}
        </div>

        <div
          data-testid="preview-pages"
          className="mx-auto flex flex-col items-center gap-4"
          style={{ width: PAGE_WIDTH * scale }}
        >
          {laidOut.map((indices, pageIndex) => (
            <div
              key={pageIndex}
              style={{ width: PAGE_WIDTH * scale, height: PAGE_HEIGHT * scale }}
            >
              <div
                className="shadow-lg"
                style={{ ...pageStyle, transform: `scale(${scale})`, transformOrigin: 'top left' }}
              >
                {indices.map((index, position) => (
                  <div
                    key={blocks[index].key}
                    style={{
                      ...BLOCK_WRAPPER,
                      // Dropped at the top of a page, matching how pagination
                      // costed it and how the export lays out.
                      marginTop: position === 0 ? 0 : blocks[index].lead,
                    }}
                  >
                    {blocks[index].node}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
