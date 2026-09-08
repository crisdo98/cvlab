import { describe, expect, it } from 'vitest';
import { ApiError, readErrorDetail } from '../api';
import { friendlyMessage } from '../errors';

/**
 * FastAPI answers a validation failure with `detail` as an array of objects.
 * Rendering that straight into a toast produced "[object Object]" on screen,
 * which is the bug these cover.
 */
describe('readErrorDetail', () => {
  it('renders a FastAPI validation array as field: message', () => {
    const body = {
      detail: [
        {
          type: 'enum',
          loc: ['body', 'provider'],
          msg: "Input should be 'openai', 'anthropic', 'bedrock' or 'local'",
        },
      ],
    };

    expect(readErrorDetail(body)).toBe(
      "provider: Input should be 'openai', 'anthropic', 'bedrock' or 'local'"
    );
  });

  it('joins several validation failures', () => {
    const body = {
      detail: [
        { loc: ['body', 'model'], msg: 'Field required' },
        { loc: ['body', 'temperature'], msg: 'Input should be less than 2' },
      ],
    };

    expect(readErrorDetail(body)).toBe(
      'model: Field required; temperature: Input should be less than 2'
    );
  });

  it('drops the request-part segment from the field path', () => {
    const body = { detail: [{ loc: ['query', 'template_id'], msg: 'Field required' }] };
    expect(readErrorDetail(body)).toBe('template_id: Field required');
  });

  it('handles a plain string detail', () => {
    expect(readErrorDetail({ detail: 'LLM features are disabled.' })).toBe(
      'LLM features are disabled.'
    );
  });

  it('falls back to message', () => {
    expect(readErrorDetail({ message: 'Something broke' })).toBe('Something broke');
  });

  it('returns null when there is nothing readable', () => {
    expect(readErrorDetail({})).toBeNull();
    expect(readErrorDetail(null)).toBeNull();
    expect(readErrorDetail({ detail: [] })).toBeNull();
    expect(readErrorDetail({ detail: [{}] })).toBeNull();
  });

  it('accepts a bare string body', () => {
    expect(readErrorDetail('plain text error')).toBe('plain text error');
  });
});

describe('friendlyMessage with validation errors', () => {
  it('never surfaces [object Object]', () => {
    const error = new ApiError('Request failed with status 422', 422, {
      detail: [{ loc: ['body', 'provider'], msg: 'Input should be one of the allowed values' }],
    });

    const message = friendlyMessage(error);
    expect(message).not.toContain('[object Object]');
    expect(message).toBe('provider: Input should be one of the allowed values');
  });
});
