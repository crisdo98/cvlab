'use client';

import { create } from 'zustand';

export type ToastKind = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
  /** 0 means it stays until dismissed. */
  duration: number;
}

/**
 * Durations match the Vue app: errors persist until dismissed, warnings sit
 * for 5s, everything else clears after 3s.
 */
const DEFAULT_DURATION: Record<ToastKind, number> = {
  success: 3000,
  error: 0,
  warning: 5000,
  info: 3000,
};

let nextId = 0;

interface ToastState {
  toasts: Toast[];
  push: (message: string, kind?: ToastKind, duration?: number) => number;
  dismiss: (id: number) => void;
  success: (message: string, duration?: number) => number;
  error: (message: string, duration?: number) => number;
  warning: (message: string, duration?: number) => number;
  info: (message: string, duration?: number) => number;
}

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],

  push: (message, kind = 'info', duration) => {
    const id = nextId++;
    const ms = duration ?? DEFAULT_DURATION[kind];
    set((state) => ({ toasts: [...state.toasts, { id, message, kind, duration: ms }] }));

    if (ms > 0) {
      setTimeout(() => get().dismiss(id), ms);
    }
    return id;
  },

  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),

  success: (message, duration) => get().push(message, 'success', duration),
  error: (message, duration) => get().push(message, 'error', duration),
  warning: (message, duration) => get().push(message, 'warning', duration),
  info: (message, duration) => get().push(message, 'info', duration),
}));

/** Imperative access for non-component code (API error handlers, stores). */
export const toast = {
  success: (m: string, d?: number) => useToastStore.getState().success(m, d),
  error: (m: string, d?: number) => useToastStore.getState().error(m, d),
  warning: (m: string, d?: number) => useToastStore.getState().warning(m, d),
  info: (m: string, d?: number) => useToastStore.getState().info(m, d),
};
