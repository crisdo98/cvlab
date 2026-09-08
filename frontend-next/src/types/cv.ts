/**
 * TypeScript interfaces for CV data structure
 * 
 * These interfaces match the Pydantic models in the backend and provide
 * type safety for CV data throughout the frontend application.
 */

// ============================================================================
// CV Section Management Types (Flexible Structure)
// ============================================================================

/**
 * Enumeration of available section types.
 * Matches backend SectionType enum.
 */
export enum SectionType {
  PERSONAL_INFO = "personal_info",
  SUMMARY = "summary",
  EXPERIENCE = "experience",
  EDUCATION = "education",
  SKILLS = "skills",
  LANGUAGES = "languages",
  SOFTWARE = "software",
  CERTIFICATIONS = "certifications",
  ACCOMPLISHMENTS = "accomplishments",
  AFFILIATIONS = "affiliations",
  INTERESTS = "interests",
  WEBSITES = "websites",
  CUSTOM = "custom"
}

/**
 * A single item in a list section.
 */
export interface ListItem {
  text: string;
}

/**
 * Content for list-based sections (Skills, Languages, Software, Interests).
 */
export interface ListSectionContent {
  content_type: "list";
  items: ListItem[];
}

/**
 * A single work experience entry.
 */
export interface ExperienceEntry {
  id: string;
  title: string;
  company?: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  current?: boolean;
  description?: string;
  achievements: string[];
}

/**
 * A single education entry.
 */
export interface EducationEntry {
  id: string;
  degree: string;
  institution: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  gpa?: string;
  description?: string;
}

/**
 * A single certification entry.
 */
export interface CertificationEntry {
  id: string;
  name: string;
  issuer: string;
  date?: string;
  expiry_date?: string;
  credential_id?: string;
}

/**
 * Content for structured entry sections (Experience, Education, Certifications).
 */
export interface StructuredSectionContent {
  content_type: "structured";
  entries: (ExperienceEntry | EducationEntry | CertificationEntry)[];
}

/**
 * Content for free-text sections (Summary, Custom sections).
 */
export interface FreeTextSectionContent {
  content_type: "free_text";
  text: string;
}

/**
 * Content for personal information section.
 */
export interface PersonalInfoContent {
  content_type: "personal";
  cv_title?: string;
  full_name: string;
  email: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  website?: string;
  title?: string;
}

/**
 * Union type for all section content types.
 * Uses discriminated union with content_type field.
 */
export type SectionContent =
  | PersonalInfoContent
  | FreeTextSectionContent
  | ListSectionContent
  | StructuredSectionContent;

/**
 * A section in a CV with type-specific content.
 */
export interface Section {
  id: string;
  type: SectionType;
  title: string;
  visible: boolean;
  order: number;
  content: SectionContent;
}

/**
 * CV model with flexible section structure (version 2).
 */
export interface CVWithSections {
  id: string;
  /** Null for the local single-user setup. */
  user_id: string | null;
  sections: Section[];
  created_at: string;
  updated_at: string;
  version: 2;
  /** Present on every CV the backend returns; shape owned by the typography API. */
  typography?: Record<string, unknown> | null;
  applied_template_id?: string | null;
}

// Type guards for section content types

/**
 * Type guard to check if content is PersonalInfoContent.
 */
export function isPersonalInfoContent(content: SectionContent): content is PersonalInfoContent {
  return content.content_type === "personal";
}

/**
 * Type guard to check if content is FreeTextSectionContent.
 */
export function isFreeTextContent(content: SectionContent): content is FreeTextSectionContent {
  return content.content_type === "free_text";
}

/**
 * Type guard to check if content is ListSectionContent.
 */
export function isListContent(content: SectionContent): content is ListSectionContent {
  return content.content_type === "list";
}

/**
 * Type guard to check if content is StructuredSectionContent.
 */
export function isStructuredContent(content: SectionContent): content is StructuredSectionContent {
  return content.content_type === "structured";
}

/**
 * Type guard to check if entry is ExperienceEntry.
 */
export function isExperienceEntry(entry: any): entry is ExperienceEntry {
  return entry && typeof entry.title === "string" && typeof entry.company === "string";
}

/**
 * Type guard to check if entry is EducationEntry.
 */
export function isEducationEntry(entry: any): entry is EducationEntry {
  return entry && typeof entry.degree === "string" && typeof entry.institution === "string";
}

/**
 * Type guard to check if entry is CertificationEntry.
 */
export function isCertificationEntry(entry: any): entry is CertificationEntry {
  return entry && typeof entry.name === "string" && typeof entry.issuer === "string";
}

/**
 * Type guard to check if section is a core section (cannot be removed).
 */
export function isCoreSection(section: Section): boolean {
  return section.type === SectionType.PERSONAL_INFO;
}

/**
 * Helper to get visible sections sorted by order.
 */
export function getVisibleSections(cv: CVWithSections): Section[] {
  return cv.sections
    .filter(section => section.visible)
    .sort((a, b) => a.order - b.order);
}

/**
 * Helper to find section by ID.
 */
export function getSectionById(cv: CVWithSections, sectionId: string): Section | undefined {
  return cv.sections.find(section => section.id === sectionId);
}

/**
 * Helper to find section by type (for predefined sections).
 */
export function getSectionByType(cv: CVWithSections, sectionType: SectionType): Section | undefined {
  return cv.sections.find(section => section.type === sectionType);
}

// API Request/Response interfaces for section management

/**
 * Request to add a predefined section type.
 */
export interface AddPredefinedSectionRequest {
  section_type: SectionType;
}

/**
 * Request to add a custom section.
 */
export interface AddCustomSectionRequest {
  title: string;
}

/**
 * Request to reorder sections.
 */
export interface ReorderSectionsRequest {
  section_ids: string[];
}

/**
 * Request to toggle section visibility.
 */
export interface ToggleVisibilityRequest {
  visible: boolean;
}

/**
 * Response containing a single section.
 */
export interface SectionResponse {
  section: Section;
  message?: string;
}

// ============================================================================
// Legacy CV Types (Fixed Structure - Version 1)
// ============================================================================

// Contact information interface
export interface ContactInfo {
  address?: string;
  phone?: string;
  email?: string;
  linkedin?: string;
  website?: string;
}

// Personal information interface
export interface PersonalInfo {
  name: string;
  title?: string;
  contact: ContactInfo;
}

// CV metadata interface
export interface CVMetadata {
  title: string;
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
  template_id: string;
}

// Work experience interface
export interface Experience {
  id: string;
  title: string;
  company: string;
  location?: string;
  start_date: string;
  end_date?: string;
  current: boolean;
  description?: string;
  achievements: string[];
}

// Education interface
export interface Education {
  id: string;
  degree: string;
  institution: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  gpa?: string;
  description?: string;
}

// Skill category interface
export interface SkillCategory {
  name: string;
  skills: string[];
}

// Skills interface
export interface Skills {
  categories: SkillCategory[];
}

// Certification interface
export interface Certification {
  id: string;
  name: string;
  issuer: string;
  date?: string;
  expiry_date?: string;
}

// Main CV model interface
export interface CVModel {
  id: string;
  metadata: CVMetadata;
  personal_info: PersonalInfo;
  summary?: string;
  experience: Experience[];
  education: Education[];
  skills: Skills;
  certifications: Certification[];
}

// API Request/Response interfaces

// Create CV request interface
export interface CVCreateRequest {
  metadata: CVMetadata;
  personal_info: PersonalInfo;
  summary?: string;
  experience?: Experience[];
  education?: Education[];
  skills?: Skills;
  certifications?: Certification[];
}

// Update CV request interface (all fields optional for partial updates)
export interface CVUpdateRequest {
  metadata?: Partial<CVMetadata>;
  personal_info?: Partial<PersonalInfo>;
  summary?: string;
  experience?: Experience[];
  education?: Education[];
  skills?: Skills;
  certifications?: Certification[];
}

// CV list response interface
export interface CVListResponse {
  cvs: CVModel[];
  total: number;
}

// Single CV response interface
export interface CVResponse {
  cv: CVModel;
  message?: string;
}

// API Error response interface
export interface APIError {
  detail: string;
  status_code: number;
}

// Form validation error interface
export interface ValidationError {
  field: string;
  message: string;
}

// Export-related interfaces (for future use)
export interface ExportRequest {
  cv_id: string;
  format: 'pdf' | 'docx' | 'txt';
  template_id?: string;
}

export interface ExportResponse {
  file_id: string;
  download_url: string;
  format: string;
  created_at: string;
}

export interface ExportHistoryItem {
  file_id: string;
  format: string;
  created_at: string;
  download_url: string;
  file_size?: number;
}

export interface ExportHistoryResponse {
  exports: ExportHistoryItem[];
  total: number;
}

// Template-related interfaces (for future use)
export interface Template {
  id: string;
  name: string;
  description?: string;
  preview_url?: string;
}

export interface TemplateListResponse {
  templates: Template[];
}

// Utility types for form handling
export type CVFormData = Omit<CVModel, 'id' | 'metadata'> & {
  metadata: Omit<CVMetadata, 'created_at' | 'updated_at'>;
};

// Type guards for runtime type checking
export function isCVModel(obj: any): obj is CVModel {
  return (
    obj &&
    typeof obj.id === 'string' &&
    obj.metadata &&
    obj.personal_info &&
    obj.personal_info.name &&
    Array.isArray(obj.experience) &&
    Array.isArray(obj.education) &&
    obj.skills &&
    Array.isArray(obj.skills.categories) &&
    Array.isArray(obj.certifications)
  );
}

export function isAPIError(obj: any): obj is APIError {
  return obj && typeof obj.detail === 'string' && typeof obj.status_code === 'number';
}

// Default/empty objects for form initialization
export const defaultContactInfo: ContactInfo = {
  address: '',
  phone: '',
  email: '',
  linkedin: '',
  website: ''
};

export const defaultPersonalInfo: PersonalInfo = {
  name: '',
  title: '',
  contact: { ...defaultContactInfo }
};

export const defaultExperience: Omit<Experience, 'id'> = {
  title: '',
  company: '',
  location: '',
  start_date: '',
  end_date: '',
  current: false,
  description: '',
  achievements: []
};

export const defaultEducation: Omit<Education, 'id'> = {
  degree: '',
  institution: '',
  location: '',
  start_date: '',
  end_date: '',
  gpa: '',
  description: ''
};

export const defaultSkillCategory: SkillCategory = {
  name: '',
  skills: []
};

export const defaultSkills: Skills = {
  categories: []
};

export const defaultCertification: Omit<Certification, 'id'> = {
  name: '',
  issuer: '',
  date: '',
  expiry_date: ''
};

export const defaultCVMetadata: Omit<CVMetadata, 'created_at' | 'updated_at'> = {
  title: '',
  template_id: 'default'
};

export const defaultCVFormData: CVFormData = {
  metadata: { ...defaultCVMetadata },
  personal_info: { ...defaultPersonalInfo },
  summary: '',
  experience: [],
  education: [],
  skills: { ...defaultSkills },
  certifications: []
};