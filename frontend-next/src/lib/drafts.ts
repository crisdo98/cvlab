'use client';

import { create } from 'zustand';
import type { CVWithSections, Section, SectionContent } from '@/types/cv';

/**
 * Unsaved section edits, keyed by section id.
 *
 * The live preview reads saved sections with these layered on top, so it tracks
 * the form as it is typed into. Nothing here reaches the backend: the section
 * editor's own Save does that, and a successful save clears the draft.
 *
 * This is deliberately separate from the section content the editors read. If
 * drafts were written back into that, every keystroke would re-render the form
 * from its own output and fight the cursor.
 */
interface DraftState {
  drafts: Record<string, SectionContent>;
  setDraft: (sectionId: string, content: SectionContent) => void;
  clearDraft: (sectionId: string) => void;
  clearAll: () => void;
}

export const useDraftStore = create<DraftState>((set) => ({
  drafts: {},

  setDraft: (sectionId, content) =>
    set((state) => ({ drafts: { ...state.drafts, [sectionId]: content } })),

  clearDraft: (sectionId) =>
    set((state) => {
      if (!(sectionId in state.drafts)) return state;
      const next = { ...state.drafts };
      delete next[sectionId];
      return { drafts: next };
    }),

  clearAll: () => set({ drafts: {} }),
}));

/** True while any section has unsaved edits. */
export function useHasDrafts(): boolean {
  return useDraftStore((state) => Object.keys(state.drafts).length > 0);
}

/** Saved sections with any in-progress edit layered over them. */
export function applyDrafts(
  cv: CVWithSections | undefined,
  drafts: Record<string, SectionContent>
): Section[] {
  if (!cv?.sections) return [];
  return cv.sections.map((section) =>
    drafts[section.id] ? { ...section, content: drafts[section.id] } : section
  );
}
