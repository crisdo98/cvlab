'use client';

import { create } from 'zustand';

import { THEME_KEY } from './theme.constants';

/** Same key the Vue app used, so an existing preference carries over. */
export { THEME_KEY };

export type Theme = 'light' | 'dark' | 'auto';

const THEMES: Theme[] = ['light', 'dark', 'auto'];

function systemPrefersDark(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches === true
  );
}

function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return;
  const dark = theme === 'dark' || (theme === 'auto' && systemPrefersDark());
  document.documentElement.classList.toggle('dark', dark);
}

interface ThemeState {
  theme: Theme;
  /** Resolved appearance, with `auto` collapsed to what is actually shown. */
  isDark: boolean;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  /** Called once from the shell; safe to call again. */
  init: () => () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: 'light',
  isDark: false,

  setTheme: (theme) => {
    if (!THEMES.includes(theme)) return;
    applyTheme(theme);
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Private browsing or blocked storage: the theme still applies for now.
    }
    set({ theme, isDark: theme === 'dark' || (theme === 'auto' && systemPrefersDark()) });
  },

  toggleTheme: () => {
    get().setTheme(get().isDark ? 'light' : 'dark');
  },

  init: () => {
    let stored: Theme | null = null;
    try {
      const raw = localStorage.getItem(THEME_KEY);
      if (raw && THEMES.includes(raw as Theme)) stored = raw as Theme;
    } catch {
      // Ignore unreadable storage.
    }

    const theme = stored ?? 'light';
    applyTheme(theme);
    set({ theme, isDark: theme === 'dark' || (theme === 'auto' && systemPrefersDark()) });

    // Track the OS preference while the theme is `auto`.
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!media) return () => {};

    const onChange = () => {
      if (get().theme !== 'auto') return;
      applyTheme('auto');
      set({ isDark: systemPrefersDark() });
    };

    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  },
}));
