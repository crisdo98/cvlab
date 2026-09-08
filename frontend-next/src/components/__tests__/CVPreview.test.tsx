import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';

/**
 * The preview measures every block off-screen before packing it into pages, so
 * each piece of content exists twice in the DOM. Queries are scoped to the
 * visible pages; the hidden pass is aria-hidden and not what a reader sees.
 */
const pages = () => within(screen.getByTestId('preview-pages'));
import { CVPreview, paginate } from '../CVPreview';
import type { Section } from '@/types/cv';

const personal = (): Section =>
  ({
    id: 'p',
    type: 'personal_info',
    title: 'Personal Information',
    order: 0,
    visible: true,
    content: {
      content_type: 'personal',
      full_name: 'Jane Doe',
      title: 'Head of Data Engineering',
      email: 'chris@example.com',
      location: 'Kent',
    },
  }) as unknown as Section;

const summary = (text: string, visible = true, order = 1): Section =>
  ({
    id: 's',
    type: 'summary',
    title: 'Professional Summary',
    order,
    visible,
    content: { content_type: 'free_text', text },
  }) as unknown as Section;

const experience = (): Section =>
  ({
    id: 'e',
    type: 'experience',
    title: 'Work Experience',
    order: 2,
    visible: true,
    content: {
      content_type: 'structured',
      entries: [
        {
          id: 'e1',
          title: 'Head of Data Engineering',
          company: 'Direct Line Group',
          location: 'London',
          start_date: 'March 2023',
          current: true,
          description: 'Strategic leader.',
          achievements: ['400% productivity increase'],
        },
      ],
    },
  }) as unknown as Section;

const noop = vi.fn();

describe('CVPreview', () => {
  it('renders the person as the document heading', () => {
    render(<CVPreview sections={[personal()]} zoom={100} onZoom={noop} />);

    expect(pages().getByText('Jane Doe')).toBeInTheDocument();
    expect(pages().getByText('Head of Data Engineering')).toBeInTheDocument();
    expect(pages().getByText(/Kent/)).toBeInTheDocument();
  });

  it('renders section bodies under their titles', () => {
    render(
      <CVPreview sections={[personal(), summary('Transformational leader.')]} zoom={100} onZoom={noop} />
    );

    expect(pages().getByText('Professional Summary')).toBeInTheDocument();
    expect(pages().getByText('Transformational leader.')).toBeInTheDocument();
  });

  it('leaves hidden sections out of the document', () => {
    render(
      <CVPreview
        sections={[personal(), summary('Should not appear', false)]}
        zoom={100}
        onZoom={noop}
      />
    );

    expect(pages().queryByText('Should not appear')).not.toBeInTheDocument();
  });

  it('renders structured entries with their achievements', () => {
    render(<CVPreview sections={[personal(), experience()]} zoom={100} onZoom={noop} />);

    expect(pages().getByText('Direct Line Group')).toBeInTheDocument();
    expect(pages().getByText('400% productivity increase')).toBeInTheDocument();
    expect(pages().getByText(/Present/)).toBeInTheDocument();
  });

  it('orders sections by their order field, not array position', () => {
    const first = summary('Comes second', true, 5);
    const second = { ...summary('Comes first', true, 1), id: 'other' } as Section;

    render(<CVPreview sections={[first, second]} zoom={100} onZoom={noop} />);

    const text = document.body.textContent ?? '';
    expect(text.indexOf('Comes first')).toBeLessThan(text.indexOf('Comes second'));
  });

  it('reports zoom changes and stops at the bounds', async () => {
    const onZoom = vi.fn();
    const { rerender } = render(
      <CVPreview sections={[personal()]} zoom={45} onZoom={onZoom} />
    );

    screen.getByLabelText('Zoom in').click();
    expect(onZoom).toHaveBeenCalledWith(50);

    rerender(<CVPreview sections={[personal()]} zoom={30} onZoom={onZoom} />);
    expect(screen.getByLabelText('Zoom out')).toBeDisabled();
  });
});

describe('paginate', () => {
  it('keeps everything on one page when it fits', () => {
    expect(paginate([100, 200, 300], 1000)).toEqual([[0, 1, 2]]);
  });

  it('starts a new page when the next block would overflow', () => {
    expect(paginate([600, 600, 600], 1000)).toEqual([[0], [1], [2]]);
  });

  it('fills a page before moving on', () => {
    expect(paginate([400, 400, 400, 400], 1000)).toEqual([
      [0, 1],
      [2, 3],
    ]);
  });

  it('gives a block taller than the page its own page rather than looping', () => {
    expect(paginate([100, 5000, 100], 1000)).toEqual([[0], [1], [2]]);
  });

  it('returns a single empty page for no content', () => {
    expect(paginate([], 1000)).toEqual([[]]);
  });

  it('treats unmeasured blocks as weightless rather than dropping them', () => {
    // jsdom and a first paint both report 0; the blocks must still render.
    expect(paginate([0, 0, 0], 1000)).toEqual([[0, 1, 2]]);
  });
});

describe('paginate with leading margins', () => {
  it('does not charge a leading margin at the top of a page', () => {
    // A section heading's top margin collapses away at a page top. Counting it
    // made each section look too tall to fit and pushed it onto its own page.
    const items = [
      { height: 500, lead: 0 },
      { height: 500, lead: 400 },
    ];
    expect(paginate(items, 1000)).toEqual([[0], [1]]);
  });

  it('charges the margin when the block follows content', () => {
    const items = [
      { height: 400, lead: 0 },
      { height: 400, lead: 300 },
    ];
    // 400 + 300 + 400 exceeds 1000, so the second block moves to page two.
    expect(paginate(items, 1000)).toEqual([[0], [1]]);
  });

  it('keeps blocks together when they genuinely fit', () => {
    const items = [
      { height: 300, lead: 0 },
      { height: 300, lead: 20 },
      { height: 300, lead: 20 },
    ];
    expect(paginate(items, 1000)).toEqual([[0, 1, 2]]);
  });

  it('still accepts plain numbers', () => {
    expect(paginate([400, 400], 1000)).toEqual([[0, 1]]);
  });
});

describe('hiding a section', () => {
  it('renders without crashing when sections shrink', () => {
    // Page indices are measured in an effect, so for one render they can point
    // past the end of a shrunken block list. That threw "This page couldn't
    // load" when a section was hidden.
    const { rerender } = render(
      <CVPreview sections={[personal(), summary('Text'), experience()]} zoom={100} onZoom={() => {}} />
    );
    expect(() =>
      rerender(<CVPreview sections={[personal()]} zoom={100} onZoom={() => {}} />)
    ).not.toThrow();
  });
});

describe('content flows across pages', () => {
  it('fills the rest of a page before starting a new one', () => {
    // The reported bug: a section whose first entry was taller than the space
    // left moved wholesale to the next page, leaving most of page one blank.
    // With fine-grained blocks the bullets flow instead.
    // 600 + (60 + 20) + 11x44 = 1164, so it cannot all fit on one page.
    const summary = { height: 600, lead: 0 };
    const heading = { height: 60, lead: 20 };
    const bullets = Array.from({ length: 11 }, () => ({ height: 44, lead: 0 }));

    const pages = paginate([summary, heading, ...bullets], 1000);

    expect(pages).toHaveLength(2);
    // Page one keeps the summary, the heading and the bullets that fit —
    // rather than pushing the whole section over and leaving 400px blank.
    expect(pages[0].length).toBeGreaterThan(3);
    expect(pages[0]).toContain(1);
  });

  it('does not strand a heading alone at the foot of a page', () => {
    const filler = { height: 950, lead: 0 };
    const heading = { height: 60, lead: 20 };
    const body = { height: 100, lead: 0 };

    const pages = paginate([filler, heading, body], 1000);
    // The heading moves to page two rather than sitting alone under the filler.
    expect(pages[0]).toEqual([0]);
    expect(pages[1]).toEqual([1, 2]);
  });

  it('an oversized single block still gets a page', () => {
    expect(paginate([{ height: 2000, lead: 0 }], 1000)).toEqual([[0]]);
  });
});
