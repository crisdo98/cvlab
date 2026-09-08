/**
 * TypeScript interfaces for Job Application Tracker
 * 
 * These interfaces match the Pydantic models in the backend and provide
 * type safety for application tracker data throughout the frontend application.
 */

// Stage enumeration matching backend Stage enum
export enum Stage {
  WISHLIST = "wishlist",
  APPLIED = "applied",
  INTERVIEW = "interview",
  OFFER = "offer",
  REJECTED = "rejected"
}

// Interview details interface
export interface Interview {
  id: string;
  date: string; // ISO datetime string
  type: string; // "phone", "video", "onsite", "technical", etc.
  meeting_link?: string;
  notes?: string;
  interviewer_name?: string;
}

// Status history entry interface
export interface StatusHistoryEntry {
  id: string;
  application_id: string;
  from_stage?: Stage; // undefined/null for initial creation
  to_stage: Stage;
  timestamp: string; // ISO datetime string
  notes?: string;
}

// Main Application model interface
export interface Application {
  id: string;
  company_name: string;
  position_title: string;
  stage: Stage;
  application_date: string; // ISO datetime string
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
  
  // Optional fields
  job_description_url?: string;
  application_deadline?: string; // ISO datetime string
  
  // Contact information
  recruiter_name?: string;
  recruiter_email?: string;
  recruiter_phone?: string;
  hiring_manager_name?: string;
  
  // Interviews
  interviews: Interview[];
  
  // Notes and tracking
  notes?: string;
  tasks: string[];
  
  // Outcome
  feedback?: string;
  outcome?: string;
  
  // CV association
  cv_version_id?: string;
  
  // Follow-up
  follow_up_date?: string; // ISO datetime string
}

// API Request/Response interfaces

// Create application request interface
export interface CreateApplicationRequest {
  company_name: string;
  position_title: string;
  stage?: Stage; // defaults to WISHLIST
  application_date: string; // ISO datetime string
  job_description_url?: string;
  application_deadline?: string; // ISO datetime string
  recruiter_name?: string;
  recruiter_email?: string;
  recruiter_phone?: string;
  hiring_manager_name?: string;
  interviews?: Interview[];
  notes?: string;
  tasks?: string[];
  feedback?: string;
  outcome?: string;
  cv_version_id?: string;
  follow_up_date?: string; // ISO datetime string
}

// Update application request interface (all fields optional for partial updates)
export interface UpdateApplicationRequest {
  company_name?: string;
  position_title?: string;
  stage?: Stage;
  application_date?: string; // ISO datetime string
  job_description_url?: string;
  application_deadline?: string; // ISO datetime string
  recruiter_name?: string;
  recruiter_email?: string;
  recruiter_phone?: string;
  hiring_manager_name?: string;
  interviews?: Interview[];
  notes?: string;
  tasks?: string[];
  feedback?: string;
  outcome?: string;
  cv_version_id?: string;
  follow_up_date?: string; // ISO datetime string
}

// Stage change request interface
export interface StageChangeRequest {
  new_stage: Stage;
  notes?: string;
}

// Bulk stage change request interface
export interface BulkStageChangeRequest {
  application_ids: string[];
  new_stage: Stage;
}

// Bulk delete request interface
export interface BulkDeleteRequest {
  application_ids: string[];
}

// Bulk operation response interface
export interface BulkOperationResponse {
  successful: string[];
  failed: Array<{ id: string; error: string }>;
}

// Import response interface
export interface ImportResponse {
  total_rows: number;
  successful: number;
  failed: number;
  errors: Array<{ row: number; error: string }>;
}

// Application filters interface
export interface ApplicationFilters {
  stage?: Stage;
  search?: string;
  date_from?: string; // ISO datetime string
  date_to?: string; // ISO datetime string
}

// Delete response interface
export interface DeleteResponse {
  success: boolean;
  message: string;
}

// API Error response interface
export interface APIError {
  detail: string;
  status_code?: number;
}

// Form validation error interface
export interface ValidationError {
  field: string;
  message: string;
}

// Type guards for runtime type checking
export function isApplication(obj: any): obj is Application {
  return (
    obj &&
    typeof obj.id === 'string' &&
    typeof obj.company_name === 'string' &&
    typeof obj.position_title === 'string' &&
    Object.values(Stage).includes(obj.stage) &&
    typeof obj.application_date === 'string' &&
    typeof obj.created_at === 'string' &&
    typeof obj.updated_at === 'string' &&
    Array.isArray(obj.interviews) &&
    Array.isArray(obj.tasks)
  );
}

export function isAPIError(obj: any): obj is APIError {
  return obj && typeof obj.detail === 'string';
}

export function isStage(value: any): value is Stage {
  return Object.values(Stage).includes(value);
}

// Default/empty objects for form initialization
export const defaultInterview: Omit<Interview, 'id'> = {
  date: new Date().toISOString(),
  type: 'phone',
  meeting_link: '',
  notes: '',
  interviewer_name: ''
};

export const defaultApplication: Omit<Application, 'id' | 'created_at' | 'updated_at'> = {
  company_name: '',
  position_title: '',
  stage: Stage.WISHLIST,
  application_date: new Date().toISOString(),
  job_description_url: '',
  application_deadline: undefined,
  recruiter_name: '',
  recruiter_email: '',
  recruiter_phone: '',
  hiring_manager_name: '',
  interviews: [],
  notes: '',
  tasks: [],
  feedback: '',
  outcome: '',
  cv_version_id: undefined,
  follow_up_date: undefined
};

export const defaultCreateApplicationRequest: CreateApplicationRequest = {
  company_name: '',
  position_title: '',
  stage: Stage.WISHLIST,
  application_date: new Date().toISOString(),
  interviews: [],
  tasks: []
};

// Utility functions for working with applications

/**
 * Check if an application has an upcoming interview (within next 7 days)
 */
export function hasUpcomingInterview(application: Application): boolean {
  const now = new Date();
  const sevenDaysFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  
  return application.interviews.some(interview => {
    const interviewDate = new Date(interview.date);
    return interviewDate >= now && interviewDate <= sevenDaysFromNow;
  });
}

/**
 * Check if an application deadline has passed
 */
export function isOverdue(application: Application): boolean {
  if (!application.application_deadline) {
    return false;
  }
  
  const deadline = new Date(application.application_deadline);
  const now = new Date();
  
  return deadline < now;
}

/**
 * Format application date for display
 */
export function formatApplicationDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

/**
 * Get stage display name
 */
export function getStageDisplayName(stage: Stage): string {
  const displayNames: Record<Stage, string> = {
    [Stage.WISHLIST]: 'Wishlist',
    [Stage.APPLIED]: 'Applied',
    [Stage.INTERVIEW]: 'Interview',
    [Stage.OFFER]: 'Offer',
    [Stage.REJECTED]: 'Rejected'
  };
  
  return displayNames[stage] || stage;
}

/**
 * Get stage color for UI display
 */
export function getStageColor(stage: Stage): string {
  const colors: Record<Stage, string> = {
    [Stage.WISHLIST]: 'gray',
    [Stage.APPLIED]: 'blue',
    [Stage.INTERVIEW]: 'yellow',
    [Stage.OFFER]: 'green',
    [Stage.REJECTED]: 'red'
  };
  
  return colors[stage] || 'gray';
}

/**
 * Sort applications by date (newest first)
 */
export function sortApplicationsByDate(applications: Application[]): Application[] {
  return [...applications].sort((a, b) => {
    const dateA = new Date(a.application_date);
    const dateB = new Date(b.application_date);
    return dateB.getTime() - dateA.getTime();
  });
}

/**
 * Filter applications by search query (company name or position title)
 */
export function filterApplicationsBySearch(applications: Application[], query: string): Application[] {
  if (!query || query.trim() === '') {
    return applications;
  }
  
  const lowerQuery = query.toLowerCase();
  return applications.filter(app => 
    app.company_name.toLowerCase().includes(lowerQuery) ||
    app.position_title.toLowerCase().includes(lowerQuery)
  );
}

/**
 * Filter applications by stage
 */
export function filterApplicationsByStage(applications: Application[], stage?: Stage): Application[] {
  if (!stage) {
    return applications;
  }
  
  return applications.filter(app => app.stage === stage);
}

/**
 * Filter applications by date range
 */
export function filterApplicationsByDateRange(
  applications: Application[],
  dateFrom?: string,
  dateTo?: string
): Application[] {
  let filtered = applications;
  
  if (dateFrom) {
    const fromDate = new Date(dateFrom);
    filtered = filtered.filter(app => new Date(app.application_date) >= fromDate);
  }
  
  if (dateTo) {
    const toDate = new Date(dateTo);
    filtered = filtered.filter(app => new Date(app.application_date) <= toDate);
  }
  
  return filtered;
}

/**
 * Apply all filters to applications
 */
export function applyFilters(applications: Application[], filters: ApplicationFilters): Application[] {
  let filtered = applications;
  
  if (filters.search) {
    filtered = filterApplicationsBySearch(filtered, filters.search);
  }
  
  if (filters.stage) {
    filtered = filterApplicationsByStage(filtered, filters.stage);
  }
  
  if (filters.date_from || filters.date_to) {
    filtered = filterApplicationsByDateRange(filtered, filters.date_from, filters.date_to);
  }
  
  return filtered;
}
