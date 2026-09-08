'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useDraftStore } from '@/lib/drafts';
import type { SectionContent } from '@/types/cv';

const LIVE_DELAY = 250;

/**
 * Local working copy of one section's content.
 *
 * Every editor uses this, so live preview and dirty tracking behave the same
 * everywhere rather than being reimplemented per editor. Edits stream to the
 * draft store after a short quiet period; nothing is persisted until save.
 */
export function useSectionForm<T extends SectionContent>(
  sectionId: string,
  initial: T
) {
  const setDraft = useDraftStore((s) => s.setDraft);
  const clearDraft = useDraftStore((s) => s.clearDraft);

  const [content, setContent] = useState<T>(() => structuredClone(initial));
  const [dirty, setDirty] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Re-seed when a different section is opened, or the saved content changes
  // underneath us. Keyed on the id so typing never resets the form.
  useEffect(() => {
    setContent(structuredClone(initial));
    setDirty(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sectionId]);

  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const update = useCallback(
    (updater: (draft: T) => T) => {
      setContent((current) => {
        const next = updater(current);
        setDirty(true);

        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => {
          timer.current = null;
          setDraft(sectionId, structuredClone(next));
        }, LIVE_DELAY);

        return next;
      });
    },
    [sectionId, setDraft]
  );

  /** Call after a successful save: the saved copy is now the truth. */
  const markSaved = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    clearDraft(sectionId);
    setDirty(false);
  }, [sectionId, clearDraft]);

  /** Throw away local edits and go back to what is saved. */
  const reset = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    clearDraft(sectionId);
    setContent(structuredClone(initial));
    setDirty(false);
  }, [sectionId, initial, clearDraft]);

  return { content, update, dirty, markSaved, reset };
}
