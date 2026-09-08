import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useToastStore } from '../toast';

describe('toast store', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useToastStore.setState({ toasts: [] });
  });

  it('auto-dismisses success after 3s', () => {
    useToastStore.getState().success('Section order updated');
    expect(useToastStore.getState().toasts).toHaveLength(1);

    vi.advanceTimersByTime(3000);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it('keeps errors until they are dismissed', () => {
    const id = useToastStore.getState().error('Failed to update section');

    // Well past any auto-dismiss window.
    vi.advanceTimersByTime(60_000);
    expect(useToastStore.getState().toasts).toHaveLength(1);

    useToastStore.getState().dismiss(id);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it('holds warnings for 5s', () => {
    useToastStore.getState().warning('Unsaved changes');

    vi.advanceTimersByTime(3000);
    expect(useToastStore.getState().toasts).toHaveLength(1);

    vi.advanceTimersByTime(2000);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it('stacks in the order raised', () => {
    const store = useToastStore.getState();
    store.info('first');
    store.info('second');

    expect(useToastStore.getState().toasts.map((t) => t.message)).toEqual([
      'first',
      'second',
    ]);
  });
});
