import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSectionForm } from '../useSectionForm';
import { useDraftStore } from '@/lib/drafts';
import type { FreeTextSectionContent } from '@/types/cv';

const content = (text: string): FreeTextSectionContent => ({
  content_type: 'free_text',
  text,
});

describe('useSectionForm', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useDraftStore.setState({ drafts: {} });
  });

  it('starts clean and does not touch the draft store', () => {
    const { result } = renderHook(() => useSectionForm('s1', content('original')));

    expect(result.current.dirty).toBe(false);
    expect(useDraftStore.getState().drafts).toEqual({});
  });

  it('holds edits locally before the quiet period elapses', () => {
    const { result } = renderHook(() => useSectionForm('s1', content('original')));

    act(() => {
      result.current.update((draft) => ({ ...draft, text: 'edited' }));
    });

    expect(result.current.content.text).toBe('edited');
    expect(result.current.dirty).toBe(true);
    // The preview should not have been told yet.
    expect(useDraftStore.getState().drafts.s1).toBeUndefined();
  });

  it('streams the edit to the preview once typing pauses', () => {
    const { result } = renderHook(() => useSectionForm('s1', content('original')));

    act(() => {
      result.current.update((draft) => ({ ...draft, text: 'edited' }));
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(useDraftStore.getState().drafts.s1).toEqual(content('edited'));
  });

  it('coalesces rapid edits into one draft update', () => {
    const { result } = renderHook(() => useSectionForm('s1', content('')));

    act(() => {
      result.current.update((d) => ({ ...d, text: 'a' }));
      result.current.update((d) => ({ ...d, text: 'ab' }));
      result.current.update((d) => ({ ...d, text: 'abc' }));
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(useDraftStore.getState().drafts.s1).toEqual(content('abc'));
  });

  it('clears the draft and dirty flag once saved', () => {
    const { result } = renderHook(() => useSectionForm('s1', content('original')));

    act(() => {
      result.current.update((d) => ({ ...d, text: 'edited' }));
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    act(() => {
      result.current.markSaved();
    });

    expect(result.current.dirty).toBe(false);
    expect(useDraftStore.getState().drafts.s1).toBeUndefined();
  });

  it('restores the saved content on reset', () => {
    const { result } = renderHook(() => useSectionForm('s1', content('original')));

    act(() => {
      result.current.update((d) => ({ ...d, text: 'edited' }));
    });
    act(() => {
      result.current.reset();
    });

    expect(result.current.content.text).toBe('original');
    expect(result.current.dirty).toBe(false);
    expect(useDraftStore.getState().drafts.s1).toBeUndefined();
  });

  it('does not share state with the section it was given', () => {
    const original = content('original');
    const { result } = renderHook(() => useSectionForm('s1', original));

    act(() => {
      result.current.update((d) => ({ ...d, text: 'edited' }));
    });

    expect(original.text).toBe('original');
  });

  it('re-seeds when a different section is opened', () => {
    const { result, rerender } = renderHook(
      ({ id, initial }) => useSectionForm(id, initial),
      { initialProps: { id: 's1', initial: content('first') } }
    );

    act(() => {
      result.current.update((d) => ({ ...d, text: 'edited' }));
    });

    rerender({ id: 's2', initial: content('second') });

    expect(result.current.content.text).toBe('second');
    expect(result.current.dirty).toBe(false);
  });
});
