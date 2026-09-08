/**
 * Typed client for the FastAPI backend.
 *
 * Mirrors the contracts of the Vue app's `src/services/api.js` so both
 * frontends can run against the same backend during the migration. Uses fetch
 * rather than axios: there is nothing here axios was doing for us.
 */

import type { CVWithSections, Section } from '@/types/cv';
import type {
  Application,
  CreateApplicationRequest,
  Stage,
  StageChangeRequest,
  StatusHistoryEntry,
  UpdateApplicationRequest,
} from '@/types/applicationTracker';

// The dev server runs on :3000 while the backend is on :8002; the production
// build is served from the same origin as the API.
const BASE_URL =
  process.env.NODE_ENV === 'production'
    ? '/api'
    : process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8002/api';

const DEFAULT_TIMEOUT = 30_000;
/** LLM calls routinely take minutes. */
const LLM_TIMEOUT = 180_000;

/** One FastAPI validation failure, as returned inside a 422 `detail` array. */
interface ValidationDetail {
  loc?: (string | number)[];
  msg?: string;
}

/**
 * Turns an error body into a readable line.
 *
 * FastAPI answers a validation failure with `detail` as an ARRAY of objects,
 * not a string. Assigning that straight to a message is what produced
 * "[object Object]" on screen, so each entry is rendered as "field: message".
 */
export function readErrorDetail(body: unknown): string | null {
  if (typeof body === 'string') return body;
  if (!body || typeof body !== 'object') return null;

  const { detail, message } = body as { detail?: unknown; message?: unknown };

  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    const lines = (detail as ValidationDetail[])
      .map((entry) => {
        if (typeof entry === 'string') return entry;
        if (!entry || typeof entry !== 'object') return null;
        // Drop the leading "body"/"query" segment: it names the request part,
        // not the field the person filled in.
        const field = entry.loc?.filter((part) => part !== 'body' && part !== 'query').join('.');
        if (!entry.msg) return field || null;
        return field ? `${field}: ${entry.msg}` : entry.msg;
      })
      .filter((line): line is string => Boolean(line));

    if (lines.length) return lines.join('; ');
  }

  if (typeof message === 'string') return message;
  return null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  timeout?: number;
  /** Send `body` as-is (FormData, Blob) instead of JSON-encoding it. */
  raw?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, timeout = DEFAULT_TIMEOUT, raw = false, headers, ...rest } = options;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: raw
        ? headers
        : { 'Content-Type': 'application/json', ...headers },
      body: body === undefined ? undefined : raw ? (body as BodyInit) : JSON.stringify(body),
    });

    if (!response.ok) {
      let detail: unknown;
      let message = `Request failed with status ${response.status}`;
      try {
        detail = await response.json();
        message = readErrorDetail(detail) ?? message;
      } catch {
        // A non-JSON error body is not worth failing over.
      }
      throw new ApiError(message, response.status, detail);
    }

    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(`Request timed out after ${timeout}ms`, 408);
    }
    throw new ApiError(
      error instanceof Error ? error.message : 'Network request failed',
      0
    );
  } finally {
    clearTimeout(timer);
  }
}

/* ------------------------------------------------------------------ CVs */

export interface CVListResponse {
  cvs: CVWithSections[];
}

export interface CVResponse {
  cv: CVWithSections;
  message?: string;
}

export const cvApi = {
  getAll: () => request<CVListResponse>('/cvs'),

  getById: (cvId: string) => request<CVResponse>(`/cvs/${cvId}`),

  create: (cv: Partial<CVWithSections>) =>
    request<CVResponse>('/cvs', { method: 'POST', body: cv }),

  update: (cvId: string, cv: Partial<CVWithSections>) =>
    request<CVResponse>(`/cvs/${cvId}`, { method: 'PUT', body: cv }),

  updateSections: (cvId: string, sections: Section[]) =>
    request<CVResponse>(`/cvs/${cvId}`, { method: 'PUT', body: { sections } }),

  remove: (cvId: string) =>
    request<{ message: string }>(`/cvs/${cvId}`, { method: 'DELETE' }),

  /** Create an independent copy. Ids are regenerated on the server. */
  duplicate: (cvId: string, title?: string) =>
    request<CVResponse>(
      `/cvs/${cvId}/duplicate${title ? `?title=${encodeURIComponent(title)}` : ''}`,
      { method: 'POST' }
    ),

  importFromMarkdown: (file: File, title?: string) => {
    const form = new FormData();
    form.append('file', file);
    if (title) form.append('title', title);
    // Let the browser set the multipart boundary.
    return request<CVResponse>('/cvs/import', { method: 'POST', body: form, raw: true });
  },
};

/** A section the AI parser recognised, with how sure it was. */
export interface ParsedSection {
  section_type: string;
  content: Record<string, unknown> | null;
  confidence: number;
  raw_text?: string | null;
}

export interface AIParsingResult {
  parsed_sections: ParsedSection[];
  ambiguities: unknown[];
  overall_confidence: number;
  /** Only built when confidence clears the backend's threshold. */
  cv_data: Record<string, unknown> | null;
  errors: string[];
  model?: string;
  provider?: string;
}

export const aiImportApi = {
  /** Read a document with the LLM. Slow: it makes one call per section. */
  parse: (fileContent: string, fileFormat: string, filename?: string) =>
    request<AIParsingResult>('/llm/parse-cv', {
      method: 'POST',
      body: { file_content: fileContent, file_format: fileFormat, filename },
      timeout: 600_000,
    }),

  /**
   * Create a CV from parsed data. The parser emits the flat v1 shape, which is
   * what POST /cvs takes; the backend migrates it to sections on the way in.
   */
  createFromParsed: (cvData: Record<string, unknown>) =>
    request<CVResponse>('/cvs', { method: 'POST', body: cvData }),
};

/* -------------------------------------------------------------- Sections */

export const sectionApi = {
  addPredefined: (cvId: string, sectionType: string) =>
    request<{ section: Section; message?: string }>(`/cvs/${cvId}/sections/predefined`, {
      method: 'POST',
      body: { section_type: sectionType },
    }),

  addCustom: (cvId: string, title: string) =>
    request<{ section: Section; message?: string }>(`/cvs/${cvId}/sections/custom`, {
      method: 'POST',
      body: { title: title.trim() },
    }),

  remove: (cvId: string, sectionId: string) =>
    request<{ message: string }>(`/cvs/${cvId}/sections/${sectionId}`, { method: 'DELETE' }),

  reorder: (cvId: string, sectionIds: string[]) =>
    request<{ message: string }>(`/cvs/${cvId}/sections/order`, {
      method: 'PUT',
      body: { section_ids: sectionIds },
    }),

  setVisibility: (cvId: string, sectionId: string, visible: boolean) =>
    request<{ message: string }>(`/cvs/${cvId}/sections/${sectionId}/visibility`, {
      method: 'PATCH',
      body: { visible },
    }),
};

/* --------------------------------------------------------------- Export */

export type ExportFormat = 'pdf' | 'docx' | 'txt';

export interface ExportRecord {
  export_id: string;
  cv_id: string;
  cv_title: string;
  format: ExportFormat;
  template_id: string;
  file_name: string;
  file_path: string;
  file_size?: number;
  created_at?: string;
}

/**
 * The response to running an export. Deliberately not ExportRecord: the POST
 * returns status/completed_at/download_url and, unlike a history record, no
 * file_name — which is why deriving the download name from file_path matters.
 */
export interface ExportRunResult {
  export_id: string;
  cv_id: string;
  format: ExportFormat;
  status: string;
  file_path?: string | null;
  download_url?: string | null;
  created_at?: string;
  completed_at?: string | null;
  error_message?: string | null;
  file_size?: number;
  message?: string;
}

/**
 * The name the download endpoint matches on. It looks up a file by name inside
 * the format directories, so an export id gets a 404 — the bug this exists to
 * prevent. History records carry file_name; the run response only has a path.
 */
export function exportFileName(record: {
  file_name?: string | null;
  file_path?: string | null;
  download_url?: string | null;
}): string | null {
  if (record.file_name) return record.file_name;
  for (const candidate of [record.file_path, record.download_url]) {
    if (typeof candidate === 'string' && candidate.length) {
      const name = candidate.split('/').filter(Boolean).pop();
      if (name) return name;
    }
  }
  return null;
}

export interface ExportTemplate {
  template_id: string;
  name: string;
  description: string;
  supported_formats: ExportFormat[];
  preview_available: boolean;
}

export const exportApi = {
  /** Exports are slow: pandoc/LaTeX runs server-side. */
  run: (cvId: string, format: ExportFormat) =>
    request<ExportRunResult>(`/export/${cvId}/${format}`, {
      method: 'POST',
      timeout: 120_000,
    }),

  templates: () =>
    request<{ templates: ExportTemplate[]; default_template: string }>('/export/templates'),

  history: (cvId: string) =>
    request<{ cv_id: string; exports: ExportRecord[] }>(`/export/history/${cvId}`),

  downloadUrl: (fileId: string) => `${BASE_URL}/export/download/${fileId}`,

  /**
   * Export the CV followed by its assessment and recommendations.
   *
   * Slower than a plain export: it runs the analyses first, one model call per
   * assessment, before rendering.
   */
  runWithRecommendations: (
    cvId: string,
    format: ExportFormat,
    options: {
      include_ats?: boolean;
      include_grammar?: boolean;
      industry?: string;
      job_title?: string;
      job_description?: string;
    }
  ) =>
    request<ExportRunResult>(`/export/${cvId}/recommendations/${format}`, {
      method: 'POST',
      body: options,
      timeout: 900_000,
    }),

  /**
   * Delete one exported file. The path is relative to the exports directory
   * ("pdf/jane-doe-....pdf"), which is how the file is stored.
   */
  remove: (format: string, fileName: string) =>
    request<{ message?: string }>(
      `/export/files/${encodeURIComponent(format)}/${encodeURIComponent(fileName)}`,
      { method: 'DELETE' }
    ),
};

/* ----------------------------------------------------------- Typography */

export interface TypographyTemplate {
  id: string;
  name: string;
  description: string;
  preview_image: string | null;
  typography: Record<string, unknown>;
}

export const typographyApi = {
  templates: () => request<{ templates: TypographyTemplate[] }>('/typography/templates'),

  forCV: (cvId: string) => request<Record<string, unknown>>(`/typography/cv/${cvId}/typography`),

  /** Replace this CV's typography. The whole config is sent, not a patch. */
  updateForCV: (cvId: string, typography: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/typography/cv/${cvId}/typography`, {
      method: 'PUT',
      body: typography,
    }),

  /** Save a typography config as a reusable template. */
  saveTemplate: (name: string, description: string, typography: Record<string, unknown>) =>
    request<{ message?: string; template_id?: string }>(
      `/typography/templates/save?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`,
      { method: 'POST', body: typography }
    ),

  deleteTemplate: (templateId: string) =>
    request<{ message?: string }>(`/typography/templates/${encodeURIComponent(templateId)}`, {
      method: 'DELETE',
    }),

  applyTemplate: (cvId: string, templateId: string) =>
    request<{ message?: string }>(
      `/typography/cv/${cvId}/typography/apply-template?template_id=${encodeURIComponent(templateId)}`,
      { method: 'POST' }
    ),
};

/* -------------------------------------------------------- Applications */

export const applicationApi = {
  list: () => request<Application[]>('/applications'),

  get: (id: string) => request<Application>(`/applications/${id}`),

  create: (payload: CreateApplicationRequest) =>
    request<Application>('/applications', { method: 'POST', body: payload }),

  update: (id: string, payload: UpdateApplicationRequest) =>
    request<Application>(`/applications/${id}`, { method: 'PUT', body: payload }),

  remove: (id: string) =>
    request<{ message?: string }>(`/applications/${id}`, { method: 'DELETE' }),

  /** The backend field is `new_stage`; see StageChangeRequest. */
  setStage: (id: string, stage: Stage, notes?: string) =>
    request<Application>(`/applications/${id}/stage`, {
      method: 'PATCH',
      body: { new_stage: stage, notes } satisfies StageChangeRequest,
    }),

  history: (id: string) =>
    request<StatusHistoryEntry[]>(`/applications/${id}/history`),
};

/* --------------------------------------------------------------- Backup */

export interface BackupInfo {
  filename: string;
  path: string;
  size: number;
  created_at: string;
  version?: string;
  summary?: Record<string, unknown>;
}

export const backupApi = {
  list: () => request<{ backups: BackupInfo[]; total: number }>('/backup/list'),

  create: (includeExports = false) =>
    request<{ filename: string; path: string; size: number; message?: string }>(
      '/backup/create',
      { method: 'POST', body: { include_exports: includeExports }, timeout: 120_000 }
    ),

  /** Replaces current data with the backup's contents. Not reversible. */
  restore: (filename: string) =>
    request<{ backup_version?: string; restored_items?: unknown; message?: string }>(
      `/backup/restore/${encodeURIComponent(filename)}`,
      { method: 'POST', timeout: 120_000 }
    ),

  remove: (filename: string) =>
    request<{ filename: string; message?: string }>(
      `/backup/${encodeURIComponent(filename)}`,
      { method: 'DELETE' }
    ),

  downloadUrl: (filename: string) =>
    `${BASE_URL}/backup/download/${encodeURIComponent(filename)}`,
};

/* ------------------------------------------------------------------ LLM */

export interface LLMConfig {
  provider: string;
  model: string;
  base_url: string | null;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
  consent_given: boolean;
  has_api_key: boolean;
}

export interface LLMStatus {
  enabled: boolean;
  provider: string;
  model: string;
  has_api_key: boolean;
  consent_given: boolean;
  requires_consent: boolean;
  timestamp: string;
}

export type GrammarIssueType =
  | 'grammar' | 'spelling' | 'punctuation' | 'passive_voice'
  | 'tense' | 'style' | 'clarity' | 'redundancy';

export type Priority = 'high' | 'medium' | 'low';

export interface GrammarIssue {
  id?: string;
  type: GrammarIssueType;
  location: string;
  issue_text: string;
  correction: string;
  explanation: string;
  severity: Priority;
}

export interface GrammarCheckResult {
  cv_id: string;
  issues: GrammarIssue[];
  overall_quality?: string;
  checked_at?: string;
  model?: string;
  provider?: string;
}

export interface ATSCompatibilityScore {
  overall_score: number;
  keyword_score?: number;
  formatting_score?: number;
  structure_score?: number;
  completeness_score?: number;
}

export interface ATSAnalysisResult {
  cv_id: string;
  compatibility_score: ATSCompatibilityScore;
  /**
   * Field names follow the backend's ATSRecommendation model. An earlier
   * title/description guess here meant every recommendation rendered blank.
   */
  recommendations?: {
    category?: string;
    issue?: string;
    suggestion?: string;
    impact?: string;
    priority?: Priority;
  }[];
  industry_keywords?: string[];
  present_keywords?: string[];
  missing_keywords?: string[];
  formatting_issues?: string[];
  summary: string;
  model?: string;
  provider?: string;
}

/** Both grammar and ATS analyse the whole CV, so they take the document itself. */
export interface WholeCVRequest {
  cv_id: string;
  cv_data: Record<string, unknown>;
}

export const llmApi = {
  config: () => request<LLMConfig>('/llm/config'),

  status: () => request<LLMStatus>('/llm/status'),

  updateConfig: (config: Partial<LLMConfig> & { api_key?: string }) =>
    request<LLMConfig>('/llm/config', { method: 'PUT', body: config }),

  testConnection: () =>
    request<{ success?: boolean; message?: string; detail?: string }>(
      '/llm/test-connection',
      { method: 'POST', timeout: 60_000 }
    ),

  grantConsent: () => request<unknown>('/llm/consent/grant', { method: 'POST' }),
  revokeConsent: () => request<unknown>('/llm/consent/revoke', { method: 'POST' }),

  checkGrammar: (payload: WholeCVRequest & { check_types?: GrammarIssueType[] }) =>
    request<{ result?: GrammarCheckResult } & GrammarCheckResult>('/llm/check-grammar', {
      method: 'POST',
      body: payload,
      timeout: LLM_TIMEOUT,
    }),

  analyseATS: (payload: WholeCVRequest & { industry?: string; job_title?: string }) =>
    request<{ result?: ATSAnalysisResult } & ATSAnalysisResult>('/llm/analyze-ats', {
      method: 'POST',
      body: payload,
      timeout: LLM_TIMEOUT,
    }),

  expandNotes: (payload: {
    notes: string;
    job_title: string;
    company: string;
    section_type?: string;
    target_length?: string;
    num_variations?: number;
  }) =>
    request<Record<string, unknown>>('/llm/expand-notes', {
      method: 'POST',
      body: payload,
      timeout: LLM_TIMEOUT,
    }),

  generateAchievements: (payload: {
    description?: string;
    notes?: string;
    job_title?: string;
    company?: string;
    context_info?: string;
    num_variations?: number;
  }) =>
    request<Record<string, unknown>>('/llm/generate-achievements', {
      method: 'POST',
      body: payload,
      timeout: LLM_TIMEOUT,
    }),
};

/* ------------------------------------------------------- Job suitability */

export interface SuitabilityRequest {
  cv_id: string;
  job_description: string;
  job_title?: string;
  include_improvement_suggestions?: boolean;
}

export const jobApi = {
  analyse: (payload: SuitabilityRequest) =>
    request<Record<string, unknown>>('/job-suitability/analyze-suitability', {
      method: 'POST',
      body: payload,
      timeout: LLM_TIMEOUT,
    }),
};

export const healthApi = {
  check: () => request<{ status: string }>('/health', { timeout: 5_000 }),
};
