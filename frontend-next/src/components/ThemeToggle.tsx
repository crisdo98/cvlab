'use client';

import { useThemeStore, type Theme } from '@/lib/theme';

const NEXT: Record<Theme, Theme> = { light: 'dark', dark: 'auto', auto: 'light' };
const LABEL: Record<Theme, string> = {
  light: 'Light theme',
  dark: 'Dark theme',
  auto: 'Follows system',
};

/** Cycles light → dark → auto, matching the three modes the Vue app had. */
export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);

  return (
    <button
      type="button"
      onClick={() => setTheme(NEXT[theme])}
      className="btn btn-secondary btn-icon"
      title={`${LABEL[theme]} — click for ${LABEL[NEXT[theme]].toLowerCase()}`}
      aria-label={LABEL[theme]}
    >
      {theme === 'light' && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      )}
      {theme === 'dark' && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
        </svg>
      )}
      {theme === 'auto' && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="4" width="18" height="13" rx="2" />
          <path d="M8 21h8M12 17v4" />
        </svg>
      )}
    </button>
  );
}
