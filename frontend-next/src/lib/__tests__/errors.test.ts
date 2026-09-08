import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { friendlyMessage, retry } from '../errors';

describe('friendlyMessage', () => {
  it('explains an unreachable backend', () => {
    expect(friendlyMessage(new ApiError('fetch failed', 0))).toContain('Cannot reach the backend');
  });

  it('prefers the backend detail when there is one', () => {
    const error = new ApiError('bad', 422, { detail: 'Section title already exists' });
    expect(friendlyMessage(error)).toBe('Section title already exists');
  });

  it('falls back to a status-appropriate message', () => {
    expect(friendlyMessage(new ApiError('x', 422))).toBe('The server rejected those values.');
    expect(friendlyMessage(new ApiError('x', 404))).toContain('not found');
    expect(friendlyMessage(new ApiError('x', 500))).toContain('backend hit an error');
  });

  it('surfaces a specific server explanation over a generic one', () => {
    const disabled = new ApiError('unavailable', 503, {
      detail: 'LLM features are disabled. Enable them in settings.',
    });
    expect(friendlyMessage(disabled)).toBe('LLM features are disabled. Enable them in settings.');
  });

  it('passes plain errors through', () => {
    expect(friendlyMessage(new Error('boom'))).toBe('boom');
  });

  it('uses the fallback for something unrecognisable', () => {
    expect(friendlyMessage('weird', 'Nope.')).toBe('Nope.');
  });
});

describe('retry', () => {
  it('returns the first success without waiting', async () => {
    const work = vi.fn().mockResolvedValue('ok');
    await expect(retry(work)).resolves.toBe('ok');
    expect(work).toHaveBeenCalledTimes(1);
  });

  it('retries server errors and eventually succeeds', async () => {
    const work = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('down', 503))
      .mockResolvedValue('recovered');

    await expect(retry(work, { baseDelay: 1 })).resolves.toBe('recovered');
    expect(work).toHaveBeenCalledTimes(2);
  });

  it('does not retry a client error the server already rejected', async () => {
    const work = vi.fn().mockRejectedValue(new ApiError('nope', 422));

    await expect(retry(work, { baseDelay: 1 })).rejects.toBeInstanceOf(ApiError);
    expect(work).toHaveBeenCalledTimes(1);
  });

  it('gives up after the configured attempts', async () => {
    const work = vi.fn().mockRejectedValue(new ApiError('down', 500));

    await expect(retry(work, { attempts: 2, baseDelay: 1 })).rejects.toBeInstanceOf(ApiError);
    expect(work).toHaveBeenCalledTimes(3);
  });
});
