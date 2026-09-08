'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useThemeStore } from '@/lib/theme';
import { ThemeToggle } from './ThemeToggle';
import { Toaster } from './Toaster';

const NAV = [
  { href: '/', label: 'CVs' },
  { href: '/applications/', label: 'Applications' },
  { href: '/backup/', label: 'Backup' },
];

/**
 * Global chrome. The CV editor supplies its own top bar and owns the whole
 * window, so on that route the shell steps out of the way entirely rather
 * than stacking a second header and page gutters on top of it.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const initTheme = useThemeStore((s) => s.init);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => initTheme(), [initTheme]);
  useEffect(() => setMenuOpen(false), [pathname]);

  const isEditor = pathname?.startsWith('/cv') ?? false;

  if (isEditor) {
    return (
      <div className="h-screen flex flex-col overflow-hidden bg-ground">
        {children}
        <Toaster />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-ground">
      <header className="bg-surface border-b border-line flex-shrink-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-4 h-14">
            <Link href="/" className="flex items-center gap-2.5">
              <Image src="/cvlab.png" alt="" width={28} height={28} priority />
              <span className="text-base font-semibold tracking-[-0.01em]">CVLab</span>
            </Link>

            <nav className="hidden sm:flex items-center gap-1 ml-4">
              {NAV.map((item) => {
                const active =
                  item.href === '/' ? pathname === '/' : pathname?.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    className={`px-2.5 py-1.5 rounded-control text-ui font-medium transition-colors ${
                      active
                        ? 'bg-ground-sunken text-ink'
                        : 'text-ink-muted hover:bg-line-soft hover:text-ink'
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <div className="flex-1" />

            <Link href="/settings/llm/" className="btn btn-secondary btn-icon" title="Settings">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-1.8-.3 1.6 1.6 0 00-1 1.5V21a2 2 0 11-4 0v-.1A1.6 1.6 0 009 19.4a1.6 1.6 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00.3-1.8 1.6 1.6 0 00-1.5-1H3a2 2 0 110-4h.1A1.6 1.6 0 004.6 9a1.6 1.6 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 001.8.3H9a1.6 1.6 0 001-1.5V3a2 2 0 114 0v.1a1.6 1.6 0 001 1.5 1.6 1.6 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8V9a1.6 1.6 0 001.5 1H21a2 2 0 110 4h-.1a1.6 1.6 0 00-1.5 1z" />
              </svg>
            </Link>

            <ThemeToggle />

            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              className="btn btn-secondary btn-icon sm:hidden"
              aria-expanded={menuOpen}
              aria-label="Toggle navigation"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" viewBox="0 0 24 24" aria-hidden="true">
                <path d={menuOpen ? 'M18 6L6 18M6 6l12 12' : 'M4 7h16M4 12h16M4 17h16'} />
              </svg>
            </button>
          </div>

          {menuOpen && (
            <nav className="sm:hidden flex flex-col gap-px pb-2 border-t border-line pt-2">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="px-2.5 py-2 rounded-control text-ui font-medium text-ink-muted hover:bg-line-soft hover:text-ink transition-colors"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          )}
        </div>
      </header>

      <main className="flex-1 min-h-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">{children}</div>
      </main>

      <footer className="bg-surface border-t border-line flex-shrink-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-4">
          <span className="meta-mono">Stored locally</span>
          <div className="flex-1" />
          <span className="text-meta text-ink-subtle">
            &copy; {new Date().getFullYear()} CVLab
          </span>
        </div>
      </footer>

      <Toaster />
    </div>
  );
}
