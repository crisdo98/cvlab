import { SectionType, type Section } from '@/types/cv';

/**
 * Section helpers, ported from the Vue app's `sectionManagementUtils`. The
 * behaviour is the same; the axios coupling is gone.
 */

const DEFAULT_TITLES: Record<SectionType, string> = {
  [SectionType.PERSONAL_INFO]: 'Personal Information',
  [SectionType.SUMMARY]: 'Professional Summary',
  [SectionType.EXPERIENCE]: 'Work Experience',
  [SectionType.EDUCATION]: 'Education',
  [SectionType.SKILLS]: 'Skills',
  [SectionType.LANGUAGES]: 'Languages',
  [SectionType.SOFTWARE]: 'Software & Tools',
  [SectionType.CERTIFICATIONS]: 'Certifications',
  [SectionType.ACCOMPLISHMENTS]: 'Accomplishments',
  [SectionType.AFFILIATIONS]: 'Professional Affiliations',
  [SectionType.INTERESTS]: 'Interests',
  [SectionType.WEBSITES]: 'Websites & Portfolios',
  [SectionType.CUSTOM]: 'Custom Section',
};

export function defaultSectionTitle(type: SectionType | string): string {
  const known = DEFAULT_TITLES[type as SectionType];
  if (known) return known;
  return String(type)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export const MAX_CUSTOM_TITLE = 100;

export function validateCustomSectionTitle(title: string): string[] {
  const errors: string[] = [];
  if (!title || title.trim() === '') {
    errors.push('Section title cannot be empty');
  }
  if (title && title.trim().length > MAX_CUSTOM_TITLE) {
    errors.push(`Section title must be ${MAX_CUSTOM_TITLE} characters or less`);
  }
  return errors;
}

export function validateSectionOrder(sectionIds: string[], expectedCount: number): string[] {
  const errors: string[] = [];
  if (sectionIds.length !== expectedCount) {
    errors.push(`Expected ${expectedCount} section ids, got ${sectionIds.length}`);
  }
  if (new Set(sectionIds).size !== sectionIds.length) {
    errors.push('Section order contains duplicate ids');
  }
  return errors;
}

export function sortSectionsByOrder(sections: Section[]): Section[] {
  return [...sections].sort((a, b) => a.order - b.order);
}

export function visibleSections(sections: Section[]): Section[] {
  return sortSectionsByOrder(sections.filter((section) => section.visible !== false));
}

/** Personal information is structural: the CV has nowhere to put its content otherwise. */
export function isCoreSection(section: Pick<Section, 'type'>): boolean {
  return section.type === SectionType.PERSONAL_INFO;
}

export function hasSectionType(sections: Section[], type: SectionType): boolean {
  return sections.some((section) => section.type === type);
}
