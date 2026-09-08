import { describe, expect, it } from 'vitest';
import { extractVariations } from '../useAI';

/**
 * The generation endpoints do not agree on a response shape — some return
 * `variations`, some `achievements`, some a bare `content` string, and some
 * wrap the lot in `result`. This is where that variation is absorbed, so it is
 * worth pinning down.
 */
describe('extractVariations', () => {
  it('reads a plain variations array', () => {
    expect(extractVariations({ variations: ['one', 'two'] })).toEqual(['one', 'two']);
  });

  it('reads achievements', () => {
    expect(extractVariations({ achievements: ['led a team'] })).toEqual(['led a team']);
  });

  it('unwraps a result envelope', () => {
    expect(extractVariations({ result: { variations: ['wrapped'] } })).toEqual(['wrapped']);
  });

  it('accepts a single content string', () => {
    expect(extractVariations({ content: 'just the one' })).toEqual(['just the one']);
  });

  it('reads objects carrying text or content', () => {
    expect(
      extractVariations({ variations: [{ text: 'from text' }, { content: 'from content' }] })
    ).toEqual(['from text', 'from content']);
  });

  it('trims and drops blanks', () => {
    expect(extractVariations({ variations: ['  spaced  ', '', '   '] })).toEqual(['spaced']);
  });

  it('returns nothing for shapes it does not recognise', () => {
    expect(extractVariations({ unexpected: ['x'] })).toEqual([]);
    expect(extractVariations(null)).toEqual([]);
    expect(extractVariations('a string')).toEqual([]);
    expect(extractVariations({ variations: [] })).toEqual([]);
  });

  it('prefers the first key that yields anything', () => {
    expect(
      extractVariations({ variations: [], achievements: ['fallback'] })
    ).toEqual(['fallback']);
  });
});
