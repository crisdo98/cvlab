import { describe, expect, it } from 'vitest';
import { pointsToPx, resolveTypography, PAGE_HEIGHT } from '../typography';
import { exportFileName } from '../api';
import { formatRelative } from '../cv-utils';

describe('resolveTypography', () => {
  it('converts stored points to pixels at 96dpi', () => {
    // 11pt is the stored body size; a point is 96/72 px.
    expect(pointsToPx(72)).toBe(96);
    const type = resolveTypography({ body_style: { font_size: 11 } });
    expect(type.body.fontSize).toBe(`${(11 * 96) / 72}px`);
  });

  it('converts an rgb object to a css colour', () => {
    const type = resolveTypography({ h2_style: { color: { r: 0, g: 102, b: 204 } } });
    expect(type.h2.color).toBe('rgb(0, 102, 204)');
  });

  it('turns inch margins into padding and a content box', () => {
    const type = resolveTypography({
      page_margins: { top: 1, right: 1, bottom: 1, left: 1 },
    });
    expect(type.padding).toBe('96px 96px 96px 96px');
    expect(type.contentHeight).toBe(PAGE_HEIGHT - 192);
  });

  it('gives a bare family a real fallback stack', () => {
    // Substitutes are metric-compatible faces, not just a generic keyword.
    expect(resolveTypography({ body_style: { font_family: 'Helvetica' } }).body.fontFamily).toBe(
      '"Helvetica", Arial, sans-serif'
    );
    expect(
      resolveTypography({ body_style: { font_family: 'Times New Roman' } }).body.fontFamily
    ).toBe('"Times New Roman", Times, serif');
  });

  it('falls back cleanly when a CV has no typography', () => {
    for (const input of [null, undefined, {}, 'nonsense']) {
      const type = resolveTypography(input);
      expect(type.body.fontSize).toBeTruthy();
      expect(type.contentHeight).toBeGreaterThan(0);
    }
  });
});

describe('exportFileName', () => {
  it('prefers the explicit file name from a history record', () => {
    expect(exportFileName({ file_name: 'cv.pdf', file_path: '/app/exports/pdf/other.pdf' })).toBe(
      'cv.pdf'
    );
  });

  it('derives the name from the path when the run response omits it', () => {
    // The export POST returns no file_name; using export_id here produced
    // "Export file not found", since the endpoint matches on the file name.
    expect(exportFileName({ file_path: '/app/exports/pdf/jane-doe-20260906.pdf' })).toBe(
      'jane-doe-20260906.pdf'
    );
  });

  it('falls back to the download url', () => {
    expect(exportFileName({ download_url: '/api/export/download/cv.docx' })).toBe('cv.docx');
  });

  it('returns null when there is nothing usable', () => {
    expect(exportFileName({})).toBeNull();
    expect(exportFileName({ file_path: null, download_url: null })).toBeNull();
  });
});

describe('formatRelative with backend timestamps', () => {
  it('treats a timestamp with no zone as UTC', () => {
    // The backend runs in UTC and serialises without an offset. Parsed as
    // local time, a fresh export showed as "1 hour ago" in BST.
    const naive = new Date(Date.now() - 5000).toISOString().replace('Z', '');
    expect(formatRelative(naive)).toBe('just now');
  });

  it('still honours an explicit zone', () => {
    const withZone = new Date(Date.now() - 5000).toISOString();
    expect(formatRelative(withZone)).toBe('just now');
  });
});

describe('bullet character', () => {
  it('uses the configured bullet', () => {
    // The preview drew a round bullet regardless, so a CV set to a triangle
    // showed one glyph on screen and a different one in the PDF.
    expect(resolveTypography({ bullet_style: '▸' }).bullet).toBe('▸');
  });

  it('falls back to a round bullet', () => {
    expect(resolveTypography({}).bullet).toBe('•');
    expect(resolveTypography({ bullet_style: '   ' }).bullet).toBe('•');
    expect(resolveTypography(null).bullet).toBe('•');
  });
});

describe('metric-compatible font fallbacks', () => {
  it('falls back from Liberation Sans to Arial, not generic sans', () => {
    // Liberation Sans matches Arial's metrics by design. It is installed in
    // the export container but not on a typical desktop, where a generic
    // fallback resolved to Helvetica and the preview wrapped differently from
    // the PDF — so it reported fewer pages.
    const family = resolveTypography({ body_style: { font_family: 'Liberation Sans' } }).body
      .fontFamily as string;
    expect(family).toContain('Arial');
    expect(family.indexOf('Arial')).toBeLessThan(family.indexOf('sans-serif'));
  });

  it('falls back from Liberation Serif to Times New Roman', () => {
    const family = resolveTypography({ body_style: { font_family: 'Liberation Serif' } }).body
      .fontFamily as string;
    expect(family).toContain('Times New Roman');
  });

  it('keeps an unknown family with a generic fallback', () => {
    const family = resolveTypography({ body_style: { font_family: 'Comic Sans MS' } }).body
      .fontFamily as string;
    expect(family).toBe('"Comic Sans MS", sans-serif');
  });
});
