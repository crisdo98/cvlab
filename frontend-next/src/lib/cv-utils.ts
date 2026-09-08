import type { CVWithSections, Section } from '@/types/cv';

/**
 * A V2 CV carries no top-level name: its identity lives in the personal info
 * section, as an explicit cv_title or else the person's name. The list and the
 * editor both read it from here so they cannot disagree.
 */
export function cvDisplayName(cv: Pick<CVWithSections, 'sections'>): string {
  const personal = cv.sections?.find((s) => s.type === 'personal_info');
  const content = personal?.content as
    | { cv_title?: string; full_name?: string }
    | undefined;
  return content?.cv_title || content?.full_name || 'Untitled CV';
}

/** The role line, when the personal section carries one. */
export function cvSubtitle(cv: Pick<CVWithSections, 'sections'>): string | null {
  const personal = cv.sections?.find((s) => s.type === 'personal_info');
  const content = personal?.content as { title?: string; full_name?: string } | undefined;
  // If the display name already fell back to full_name, the title is the useful line.
  return content?.title || null;
}

export function visibleSectionCount(cv: Pick<CVWithSections, 'sections'>): number {
  return (cv.sections ?? []).filter((s: Section) => s.visible !== false).length;
}

/**
 * Parse a timestamp from the API.
 *
 * The backend runs in UTC and serialises `datetime.now()` without an offset
 * ("2026-09-06T20:03:31.596931"). JavaScript reads a date-time with no offset
 * as *local* time, so every timestamp appeared shifted by the viewer's UTC
 * offset — an export made seconds ago showed as "1 hour ago" in BST. Anything
 * lacking a zone is therefore treated as UTC, which is what it is.
 */
export function parseApiDate(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value.trim());
  return new Date(hasZone ? value : `${value}Z`);
}

export function formatDateTime(value?: string | null): string {
  if (!value) return 'Unknown';
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** "3 minutes ago" style, for the most recent edit. */
export function formatRelative(value?: string | null): string {
  if (!value) return 'never';
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return 'never';

  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';

  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['minute', 60],
    ['hour', 3600],
    ['day', 86400],
    ['month', 2_592_000],
    ['year', 31_536_000],
  ];

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  let chosen: [Intl.RelativeTimeFormatUnit, number] = units[0];
  for (const unit of units) {
    if (seconds >= unit[1]) chosen = unit;
  }
  return formatter.format(-Math.round(seconds / chosen[1]), chosen[0]);
}

/** Filename-safe slug, matching the export naming used today. */
export function cvSlug(cv: Pick<CVWithSections, 'sections'>): string {
  return cvDisplayName(cv)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}
