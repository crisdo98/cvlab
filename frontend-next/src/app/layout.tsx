import type { Metadata } from 'next';
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Serif } from 'next/font/google';
import { AppShell } from '@/components/AppShell';
import { Providers } from '@/components/Providers';
import { THEME_KEY } from '@/lib/theme.constants';
import './globals.css';

// Self-hosted by next/font at build time, so the static export has no runtime
// dependency on Google Fonts.
const plexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-plex-sans',
  display: 'swap',
});

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-plex-mono',
  display: 'swap',
});

const plexSerif = IBM_Plex_Serif({
  subsets: ['latin'],
  weight: ['400', '600'],
  variable: '--font-plex-serif',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'CVLab — Test. Refine. Get Hired',
  description: 'Create, tailor and export your CV. Your data stays local.',
  icons: { icon: '/cvlab.png' },
};

/**
 * Applies the stored theme before first paint. Without this the page renders
 * light and then flips to dark after hydration.
 *
 * The string is a compile-time constant built from THEME_KEY — no user input
 * reaches it, so dangerouslySetInnerHTML carries no injection risk here. It
 * must be inline rather than an imported module: an external script would not
 * run until after the first paint, which is the whole problem being solved.
 * Defaults to light when nothing is stored, matching the Vue app.
 */
const themeScript = `(function(){try{
  var t = localStorage.getItem(${JSON.stringify(THEME_KEY)});
  var systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (t === 'dark' || (t === 'auto' && systemDark)) {
    document.documentElement.classList.add('dark');
  }
} catch (e) {}})()`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexMono.variable} ${plexSerif.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="antialiased">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
