'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, applicationApi } from '@/lib/api';
import { toast } from '@/lib/toast';
import type {
  Application,
  CreateApplicationRequest,
  Stage,
  UpdateApplicationRequest,
} from '@/types/applicationTracker';

export const applicationKeys = {
  all: ['applications'] as const,
  detail: (id: string) => ['applications', id] as const,
};

function message(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function useApplications() {
  return useQuery({
    queryKey: applicationKeys.all,
    queryFn: () => applicationApi.list(),
  });
}

export function useCreateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateApplicationRequest) => applicationApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      toast.success('Application added');
    },
    onError: (error) => toast.error(message(error, 'Could not add that application')),
  });
}

export function useUpdateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateApplicationRequest }) =>
      applicationApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      toast.success('Application updated');
    },
    onError: (error) => toast.error(message(error, 'Could not update that application')),
  });
}

export function useDeleteApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => applicationApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      toast.success('Application deleted');
    },
    onError: (error) => toast.error(message(error, 'Could not delete that application')),
  });
}

/**
 * Moving a card between columns. Applied optimistically so the drag settles
 * immediately, and rolled back if the server disagrees.
 */
export function useMoveApplication() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, stage }: { id: string; stage: Stage }) =>
      applicationApi.setStage(id, stage),

    onMutate: async ({ id, stage }) => {
      await queryClient.cancelQueries({ queryKey: applicationKeys.all });
      const previous = queryClient.getQueryData<Application[]>(applicationKeys.all);

      queryClient.setQueryData<Application[]>(applicationKeys.all, (current) =>
        (current ?? []).map((app) => (app.id === id ? { ...app, stage } : app))
      );

      return { previous };
    },

    onError: (error, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(applicationKeys.all, context.previous);
      }
      toast.error(message(error, 'Could not move that application'));
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
    },
  });
}
