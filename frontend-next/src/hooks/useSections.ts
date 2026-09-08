'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiError, cvApi, sectionApi } from '@/lib/api';
import { toast } from '@/lib/toast';
import { cvKeys } from './useCVs';
import type { Section, SectionContent } from '@/types/cv';

function message(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

/**
 * Saves one section's content. The backend takes the whole sections array on
 * PUT, so the current CV is re-read first and only the target section swapped —
 * the same approach the Vue editor used.
 */
export function useSaveSectionContent(cvId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      sectionId,
      content,
    }: {
      sectionId: string;
      content: SectionContent;
    }) => {
      if (!cvId) throw new ApiError('No CV loaded', 0);
      const { cv } = await cvApi.getById(cvId);
      const sections = cv.sections.map((section) =>
        section.id === sectionId ? { ...section, content } : section
      );
      return (await cvApi.updateSections(cvId, sections)).cv;
    },
    onSuccess: (cv) => {
      queryClient.setQueryData(cvKeys.detail(cv.id), cv);
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      toast.success('Section saved');
    },
    onError: (error) => toast.error(message(error, 'Could not save the section')),
  });
}

export function useReorderSections(cvId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sectionIds: string[]) => {
      if (!cvId) throw new ApiError('No CV loaded', 0);
      return sectionApi.reorder(cvId, sectionIds);
    },
    onSuccess: () => {
      if (cvId) queryClient.invalidateQueries({ queryKey: cvKeys.detail(cvId) });
    },
    onError: (error) => {
      toast.error(message(error, 'Could not reorder sections'));
      if (cvId) queryClient.invalidateQueries({ queryKey: cvKeys.detail(cvId) });
    },
  });
}

export function useToggleSectionVisibility(cvId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ sectionId, visible }: { sectionId: string; visible: boolean }) => {
      if (!cvId) throw new ApiError('No CV loaded', 0);
      return sectionApi.setVisibility(cvId, sectionId, visible);
    },
    onSuccess: () => {
      if (cvId) queryClient.invalidateQueries({ queryKey: cvKeys.detail(cvId) });
    },
    onError: (error) => {
      toast.error(message(error, 'Could not change visibility'));
      if (cvId) queryClient.invalidateQueries({ queryKey: cvKeys.detail(cvId) });
    },
  });
}

export function useRemoveSection(cvId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sectionId: string) => {
      if (!cvId) throw new ApiError('No CV loaded', 0);
      return sectionApi.remove(cvId, sectionId);
    },
    onSuccess: () => {
      if (cvId) queryClient.invalidateQueries({ queryKey: cvKeys.detail(cvId) });
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      toast.success('Section removed');
    },
    onError: (error) => toast.error(message(error, 'Could not remove the section')),
  });
}

export function useAddSections(cvId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      types,
      customTitle,
    }: {
      types: string[];
      customTitle?: string;
    }): Promise<Section[]> => {
      if (!cvId) throw new ApiError('No CV loaded', 0);
      const added: Section[] = [];
      // The backend adds one at a time; sequential keeps the resulting order
      // predictable rather than racing.
      for (const type of types) {
        added.push((await sectionApi.addPredefined(cvId, type)).section);
      }
      if (customTitle?.trim()) {
        added.push((await sectionApi.addCustom(cvId, customTitle)).section);
      }
      return added;
    },
    onSuccess: (added) => {
      if (cvId) queryClient.invalidateQueries({ queryKey: cvKeys.detail(cvId) });
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      toast.success(added.length === 1 ? 'Section added' : `${added.length} sections added`);
    },
    onError: (error) => toast.error(message(error, 'Could not add the section')),
  });
}
