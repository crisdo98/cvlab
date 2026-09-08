'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, cvApi } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { CVWithSections } from '@/types/cv';

export const cvKeys = {
  all: ['cvs'] as const,
  detail: (id: string) => ['cvs', id] as const,
};

function message(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function useCVList() {
  return useQuery({
    queryKey: cvKeys.all,
    queryFn: async () => (await cvApi.getAll()).cvs,
  });
}

export function useCV(cvId: string | null) {
  return useQuery({
    queryKey: cvKeys.detail(cvId ?? ''),
    queryFn: async () => (await cvApi.getById(cvId!)).cv,
    enabled: Boolean(cvId),
  });
}

export function useCreateCV() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (cv?: Partial<CVWithSections>) => (await cvApi.create(cv ?? {})).cv,
    onSuccess: (cv) => {
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      toast.success('CV created');
      return cv;
    },
    onError: (error) => toast.error(message(error, 'Could not create the CV')),
  });
}

export function useDeleteCV() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (cvId: string) => cvApi.remove(cvId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      toast.success('CV deleted');
    },
    onError: (error) => toast.error(message(error, 'Could not delete the CV')),
  });
}

export function useDuplicateCV() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (cvId: string) => cvApi.duplicate(cvId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      toast.success('CV duplicated');
    },
    onError: (error) => toast.error(message(error, 'Could not duplicate the CV')),
  });
}

export function useImportMarkdown() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ file, title }: { file: File; title?: string }) =>
      (await cvApi.importFromMarkdown(file, title)).cv,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      toast.success('CV imported');
    },
    onError: (error) => toast.error(message(error, 'Could not import that file')),
  });
}
