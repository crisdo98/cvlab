import { ApiError, readErrorDetail } from './api';

/**
 * Turns a failure into something worth showing a person.
 *
 * Ported from the two near-identical `formatErrorMessage` helpers in the Vue
 * services, which read axios's `error.response`. This reads `ApiError`, so the
 * status mapping survives the move to fetch.
 */
export function friendlyMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : fallback;
  }

  // A message from the backend beats a generic one, when there is one.
  // Handles FastAPI's array-shaped validation detail as well as a plain string.
  const detail = readErrorDetail(error.detail) ?? undefined;

  switch (error.status) {
    case 0:
      return 'Cannot reach the backend. Is it running?';
    case 400:
      return detail ?? 'Invalid request. Check the values and try again.';
    case 401:
      return 'Authentication required.';
    case 403:
      return 'You do not have permission to do that.';
    case 404:
      return detail ?? 'That was not found. It may have been deleted.';
    case 408:
      return 'The request timed out.';
    case 422:
      return detail ?? 'The server rejected those values.';
    case 429:
      return 'Too many requests. Wait a moment and try again.';
    case 500:
    case 502:
    case 503:
      // A 503 often carries something specific and actionable — "LLM features
      // are disabled", say — which beats a generic retry message.
      return detail ?? 'The backend hit an error. Try again shortly.';
    default:
      return detail ?? error.message ?? fallback;
  }
}

/**
 * Retries with exponential backoff. Ported from the Vue services, with one
 * change: client errors are not retried, since repeating a request the server
 * has already rejected as invalid only wastes time.
 */
export async function retry<T>(
  work: () => Promise<T>,
  { attempts = 3, baseDelay = 1000 }: { attempts?: number; baseDelay?: number } = {}
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= attempts; attempt++) {
    try {
      return await work();
    } catch (error) {
      lastError = error;

      const status = error instanceof ApiError ? error.status : 0;
      const worthRetrying = status === 0 || status === 408 || status === 429 || status >= 500;
      if (!worthRetrying || attempt === attempts) break;

      await new Promise((resolve) => setTimeout(resolve, baseDelay * 2 ** attempt));
    }
  }

  throw lastError;
}
