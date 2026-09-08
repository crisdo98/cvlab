import { describe, expect, it } from 'vitest';
import { cvDisplayName, cvSlug, formatRelative, visibleSectionCount } from '../cv-utils';
import type { Section } from '@/types/cv';

const personal = (content: Record<string, unknown>): Section =>
  ({
    id: 'p1',
    type: 'personal_info',
    title: 'Personal Information',
    order: 0,
    visible: true,
    content: { content_type: 'personal', ...content },
  }) as unknown as Section;

const other = (id: string, visible = true): Section =>
  ({
    id,
    type: 'summary',
    title: 'Summary',
    order: 1,
    visible,
    content: { content_type: 'free_text', text: '' },
  }) as unknown as Section;

describe('cvDisplayName', () => {
  it('prefers an explicit cv_title', () => {
    const cv = { sections: [personal({ cv_title: 'Exec CV', full_name: 'Jane Doe' })] };
    expect(cvDisplayName(cv)).toBe('Exec CV');
  });

  it('falls back to the person name when there is no title', () => {
    const cv = { sections: [personal({ full_name: 'Jane Doe' })] };
    expect(cvDisplayName(cv)).toBe('Jane Doe');
  });

  it('falls back again when the personal section is empty', () => {
    expect(cvDisplayName({ sections: [personal({})] })).toBe('Untitled CV');
  });

  it('handles a CV with no personal section at all', () => {
    expect(cvDisplayName({ sections: [] })).toBe('Untitled CV');
  });

  it('ignores an empty-string title rather than showing a blank name', () => {
    const cv = { sections: [personal({ cv_title: '', full_name: 'Jane Doe' })] };
    expect(cvDisplayName(cv)).toBe('Jane Doe');
  });
});

describe('visibleSectionCount', () => {
  it('counts only visible sections', () => {
    const cv = { sections: [personal({}), other('a'), other('b', false)] };
    expect(visibleSectionCount(cv)).toBe(2);
  });

  it('is zero for an empty CV', () => {
    expect(visibleSectionCount({ sections: [] })).toBe(0);
  });
});

describe('cvSlug', () => {
  it('makes a filename-safe slug', () => {
    const cv = { sections: [personal({ cv_title: 'Jane Doe — Exec CV' })] };
    expect(cvSlug(cv)).toBe('jane-doe-exec-cv');
  });
});

describe('formatRelative', () => {
  it('reports recent edits as just now', () => {
    expect(formatRelative(new Date().toISOString())).toBe('just now');
  });

  it('handles a missing or unparsable timestamp', () => {
    expect(formatRelative(null)).toBe('never');
    expect(formatRelative('not a date')).toBe('never');
  });
});
