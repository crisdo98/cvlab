import { describe, expect, it } from 'vitest';
import {
  defaultSectionTitle,
  hasSectionType,
  isCoreSection,
  sortSectionsByOrder,
  validateCustomSectionTitle,
  validateSectionOrder,
  visibleSections,
} from '../sections';
import { SectionType, type Section } from '@/types/cv';

const section = (id: string, order: number, visible = true, type = SectionType.SUMMARY): Section =>
  ({
    id,
    type,
    title: id,
    order,
    visible,
    content: { content_type: 'free_text', text: '' },
  }) as unknown as Section;

describe('defaultSectionTitle', () => {
  it('names the predefined types', () => {
    expect(defaultSectionTitle(SectionType.EXPERIENCE)).toBe('Work Experience');
    expect(defaultSectionTitle(SectionType.WEBSITES)).toBe('Websites & Portfolios');
  });

  it('humanises anything it does not know', () => {
    expect(defaultSectionTitle('speaking_engagements')).toBe('Speaking Engagements');
  });
});

describe('validateCustomSectionTitle', () => {
  it('accepts a normal title', () => {
    expect(validateCustomSectionTitle('Publications')).toEqual([]);
  });

  it('rejects empty and whitespace-only titles', () => {
    expect(validateCustomSectionTitle('')).toHaveLength(1);
    expect(validateCustomSectionTitle('   ')).toHaveLength(1);
  });

  it('rejects titles over 100 characters', () => {
    expect(validateCustomSectionTitle('x'.repeat(101))).toHaveLength(1);
    expect(validateCustomSectionTitle('x'.repeat(100))).toEqual([]);
  });
});

describe('validateSectionOrder', () => {
  it('accepts a complete, unique ordering', () => {
    expect(validateSectionOrder(['a', 'b', 'c'], 3)).toEqual([]);
  });

  it('catches a missing section', () => {
    expect(validateSectionOrder(['a', 'b'], 3)).toHaveLength(1);
  });

  it('catches duplicates', () => {
    expect(validateSectionOrder(['a', 'a', 'b'], 3)).toContain(
      'Section order contains duplicate ids'
    );
  });
});

describe('ordering', () => {
  it('sorts by order without mutating the input', () => {
    const input = [section('c', 2), section('a', 0), section('b', 1)];
    const sorted = sortSectionsByOrder(input);

    expect(sorted.map((s) => s.id)).toEqual(['a', 'b', 'c']);
    expect(input.map((s) => s.id)).toEqual(['c', 'a', 'b']);
  });

  it('drops hidden sections and keeps order', () => {
    const input = [section('c', 2), section('a', 0), section('b', 1, false)];
    expect(visibleSections(input).map((s) => s.id)).toEqual(['a', 'c']);
  });
});

describe('core sections', () => {
  it('treats personal info as structural', () => {
    expect(isCoreSection({ type: SectionType.PERSONAL_INFO })).toBe(true);
    expect(isCoreSection({ type: SectionType.SKILLS })).toBe(false);
  });

  it('detects whether a type is already present', () => {
    const sections = [section('a', 0, true, SectionType.SKILLS)];
    expect(hasSectionType(sections, SectionType.SKILLS)).toBe(true);
    expect(hasSectionType(sections, SectionType.EDUCATION)).toBe(false);
  });
});
