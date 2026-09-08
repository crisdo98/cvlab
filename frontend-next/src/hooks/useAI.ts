'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { llmApi, type WholeCVRequest } from '@/lib/api';
import { friendlyMessage } from '@/lib/errors';
import { toast } from '@/lib/toast';
import type { CVWithSections } from '@/types/cv';

/**
 * Whether AI features can actually run.
 *
 * Every AI call needs the provider enabled and consent given. Asking once here
 * lets each feature show why it is unavailable rather than firing a request
 * that the backend will refuse.
 */
export function useAIAvailability() {
  const status = useQuery({
    queryKey: ['llm-status'],
    queryFn: () => llmApi.status(),
    staleTime: 60_000,
  });

  const data = status.data;
  const ready = Boolean(data?.enabled && data?.consent_given);

  let reason: string | null = null;
  if (data && !data.enabled) {
    reason = 'AI features are switched off in settings.';
  } else if (data && !data.consent_given) {
    reason = 'Consent has not been given for sending CV content to the provider.';
  }

  return { ready, reason, provider: data?.provider, model: data?.model, isLoading: status.isLoading };
}

/** The whole-CV payload that grammar and ATS both take. */
function wholeCV(cv: CVWithSections): WholeCVRequest {
  return { cv_id: cv.id, cv_data: cv as unknown as Record<string, unknown> };
}

export function useGrammarCheck(cv: CVWithSections | undefined) {
  return useMutation({
    mutationFn: async () => {
      if (!cv) throw new Error('No CV loaded');
      const response = await llmApi.checkGrammar(wholeCV(cv));
      // The backend wraps some results and returns others bare.
      return response.result ?? response;
    },
    onError: (error) => toast.error(friendlyMessage(error, 'Grammar check failed')),
  });
}

export function useATSAnalysis(cv: CVWithSections | undefined) {
  return useMutation({
    mutationFn: async (options: { industry?: string; job_title?: string } = {}) => {
      if (!cv) throw new Error('No CV loaded');
      const response = await llmApi.analyseATS({ ...wholeCV(cv), ...options });
      return response.result ?? response;
    },
    onError: (error) => toast.error(friendlyMessage(error, 'ATS analysis failed')),
  });
}

/**
 * Pulls the generated strings out of a response whose exact shape varies by
 * endpoint — some return `variations`, some `achievements`, some `content`.
 */
export function extractVariations(payload: unknown): string[] {
  if (!payload || typeof payload !== 'object') return [];
  const body = (payload as { result?: unknown }).result ?? payload;
  if (!body || typeof body !== 'object') return [];

  for (const key of ['variations', 'achievements', 'content', 'suggestions', 'expanded']) {
    const value = (body as Record<string, unknown>)[key];
    if (typeof value === 'string' && value.trim()) return [value.trim()];
    if (Array.isArray(value)) {
      const strings = value
        .map((item) =>
          typeof item === 'string'
            ? item
            : typeof item === 'object' && item !== null
              ? String((item as { text?: string; content?: string }).text ??
                  (item as { content?: string }).content ?? '')
              : ''
        )
        .map((text) => text.trim())
        .filter(Boolean);
      if (strings.length) return strings;
    }
  }
  return [];
}

export function useGenerateAchievements() {
  return useMutation({
    mutationFn: async (payload: {
      description?: string;
      notes?: string;
      job_title?: string;
      company?: string;
      num_variations?: number;
    }) => extractVariations(await llmApi.generateAchievements(payload)),
    onError: (error) => toast.error(friendlyMessage(error, 'Could not generate achievements')),
  });
}

export function useExpandNotes() {
  return useMutation({
    mutationFn: async (payload: {
      notes: string;
      job_title: string;
      company: string;
      section_type?: string;
      num_variations?: number;
    }) => extractVariations(await llmApi.expandNotes(payload)),
    onError: (error) => toast.error(friendlyMessage(error, 'Could not expand those notes')),
  });
}
