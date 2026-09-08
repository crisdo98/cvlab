import type { CSSProperties } from 'react';

/**
 * Turn a CV's stored typography config into CSS for the preview.
 *
 * Applying a template updated the stored config but the preview rendered with
 * hardcoded styles, so the UI said "Applied" and nothing changed. This is the
 * translation that was missing.
 *
 * Two unit conversions matter. Font sizes are stored in points, as they are
 * for the PDF export, while the preview is a pixel canvas: at 96dpi a point is
 * 96/72 px. Page margins are stored in inches for the same reason.
 */

/** US Letter at 96dpi — the size the preview paper has always used. */
export const PAGE_WIDTH = 816;
export const PAGE_HEIGHT = 1056;

const PX_PER_INCH = 96;
const PX_PER_POINT = PX_PER_INCH / 72;

interface StoredColor {
  r?: number;
  g?: number;
  b?: number;
}

interface StoredTextStyle {
  font_family?: string;
  font_size?: number;
  font_weight?: string;
  font_style?: string;
  color?: StoredColor | string;
  line_height?: number;
  alignment?: string;
}

interface StoredMargins {
  top?: number;
  right?: number;
  bottom?: number;
  left?: number;
}

export interface ResolvedTypography {
  padding: string;
  contentWidth: number;
  contentHeight: number;
  /** Gap between paragraphs, in px. Stored in points, as the exporter uses it. */
  paragraphSpacing: number;
  /** Gap above a section heading, in px. */
  sectionSpacing: number;
  /** The bullet character. The exporter uses it too, so both must agree. */
  bullet: string;
  h1: CSSProperties;
  h2: CSSProperties;
  h3: CSSProperties;
  body: CSSProperties;
  contact: CSSProperties;
}

export function pointsToPx(points: number): number {
  return points * PX_PER_POINT;
}

function colorToCss(color: StoredColor | string | undefined, fallback: string): string {
  if (typeof color === 'string' && color.trim()) return color;
  if (color && typeof color === 'object') {
    const { r, g, b } = color;
    if ([r, g, b].every((c) => typeof c === 'number')) {
      return `rgb(${r}, ${g}, ${b})`;
    }
  }
  return fallback;
}

/**
 * A stored family name is a single face ("Helvetica"). Real fallbacks are
 * appended so the preview still renders if the face is not installed.
 */
/**
 * Metric-compatible substitutes, so the preview wraps where the PDF wraps.
 *
 * The Liberation faces exist to match the metrics of the Microsoft core fonts
 * character for character. They are installed in the export container but not
 * on a typical desktop, where a bare `sans-serif` fallback resolves to
 * Helvetica — close enough to look right, different enough that lines wrap in
 * other places and the preview reported fewer pages than the PDF produced.
 */
const METRIC_EQUIVALENTS: Record<string, string> = {
  'liberation sans': 'Arial, Helvetica',
  'liberation serif': '"Times New Roman", Times',
  'liberation mono': '"Courier New", Courier',
  helvetica: 'Helvetica, Arial',
  arial: 'Arial, Helvetica',
  'times new roman': '"Times New Roman", Times',
  georgia: 'Georgia, serif',
  palatino: 'Palatino, "Palatino Linotype", serif',
  courier: '"Courier New", Courier',
};

function familyToCss(family: string | undefined, fallback: string): string {
  if (!family || !family.trim()) return fallback;
  const name = family.trim();
  const generic = /times|georgia|garamond|palatino|serif/i.test(name) ? 'serif' : 'sans-serif';
  const equivalent = METRIC_EQUIVALENTS[name.toLowerCase()];

  const stack = [`"${name}"`];
  for (const face of (equivalent ?? '').split(',')) {
    const trimmed = face.trim();
    // Skip a substitute that only repeats the family already asked for.
    if (!trimmed || trimmed.replace(/"/g, '').toLowerCase() === name.toLowerCase()) continue;
    if (trimmed === generic) continue;
    stack.push(trimmed);
  }
  stack.push(generic);
  return stack.join(', ');
}

function textStyle(
  style: StoredTextStyle | undefined,
  defaults: {
    size: number;
    weight: string;
    color: string;
    family: string;
    lineHeight: number;
    align: CSSProperties['textAlign'];
  }
): CSSProperties {
  const size = typeof style?.font_size === 'number' ? style.font_size : defaults.size;
  return {
    fontFamily: familyToCss(style?.font_family, defaults.family),
    fontSize: `${pointsToPx(size)}px`,
    fontWeight: style?.font_weight || defaults.weight,
    fontStyle: style?.font_style && style.font_style !== 'normal' ? style.font_style : undefined,
    color: colorToCss(style?.color, defaults.color),
    lineHeight: typeof style?.line_height === 'number' ? style.line_height : defaults.lineHeight,
    textAlign: (style?.alignment as CSSProperties['textAlign']) || defaults.align,
    // LaTeX hyphenates justified text and CSS does not. Rather than let the
    // two drift, hyphenation stays off on both sides.
    hyphens: 'none',
  };
}

function inchesToPx(value: number | undefined, fallback: number): number {
  return (typeof value === 'number' ? value : fallback) * PX_PER_INCH;
}

/**
 * Resolve a stored config, falling back to the preview's previous look when a
 * CV has no typography at all.
 */
export function resolveTypography(raw: unknown): ResolvedTypography {
  const config = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const margins = (config.page_margins || {}) as StoredMargins;

  const top = inchesToPx(margins.top, 0.75);
  const right = inchesToPx(margins.right, 0.75);
  const bottom = inchesToPx(margins.bottom, 0.75);
  const left = inchesToPx(margins.left, 0.75);

  // These mirror TypographyConfig's defaults on the backend. A CV created by
  // import carries no typography at all, and when the two sides fell back to
  // different fonts and sizes the preview and the PDF simply disagreed.
  const sans = '"Liberation Sans", Helvetica, Arial, sans-serif';

  const spacing = (value: unknown, fallback: number) =>
    pointsToPx(typeof value === 'number' ? value : fallback);

  return {
    padding: `${top}px ${right}px ${bottom}px ${left}px`,
    contentWidth: PAGE_WIDTH - left - right,
    contentHeight: PAGE_HEIGHT - top - bottom,
    // The exporter turns these into \parskip and \titlespacing. The preview
    // used fixed Tailwind margins instead, so the two drifted apart as soon as
    // anyone changed them.
    paragraphSpacing: spacing(config.paragraph_spacing, 6),
    sectionSpacing: spacing(config.section_spacing, 8),
    // The preview drew a round bullet regardless, so a CV configured with a
    // triangle showed one glyph on screen and another in the PDF.
    bullet:
      typeof config.bullet_style === 'string' && config.bullet_style.trim()
        ? config.bullet_style.trim()
        : '•',
    h1: textStyle(config.h1_style as StoredTextStyle, {
      size: 24,
      weight: 'bold',
      color: 'rgb(0, 0, 0)',
      family: sans,
      lineHeight: 1.5,
      align: 'center',
    }),
    h2: textStyle(config.h2_style as StoredTextStyle, {
      size: 18,
      weight: 'bold',
      color: 'rgb(0, 0, 0)',
      family: sans,
      lineHeight: 1.5,
      align: 'left',
    }),
    h3: textStyle(config.h3_style as StoredTextStyle, {
      size: 14,
      weight: 'bold',
      color: 'rgb(0, 0, 0)',
      family: sans,
      lineHeight: 1.5,
      align: 'left',
    }),
    body: textStyle(config.body_style as StoredTextStyle, {
      size: 11,
      weight: 'normal',
      color: 'rgb(0, 0, 0)',
      family: sans,
      lineHeight: 1.5,
      align: 'justify',
    }),
    contact: textStyle((config.contact_style || config.body_style) as StoredTextStyle, {
      size: 10,
      weight: 'normal',
      color: 'rgb(60, 60, 60)',
      family: sans,
      lineHeight: 1.5,
      align: 'center',
    }),
  };
}
