import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Markdown, parseBlocks } from '../markdown';

describe('parseBlocks', () => {
  it('groups consecutive bullets into one list', () => {
    const blocks = parseBlocks('- one\n- two');
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ type: 'list', items: ['one', 'two'], ordered: false });
  });

  it('separates a paragraph from a following list', () => {
    const blocks = parseBlocks('Intro text\n- item');
    expect(blocks.map((b) => b.type)).toEqual(['paragraph', 'list']);
  });

  it('keeps ordered and unordered lists apart', () => {
    expect(parseBlocks('1. one\n- two').map((b) => b.type)).toEqual(['list', 'list']);
  });

  it('strips the hard-break backslash the exporter adds', () => {
    const blocks = parseBlocks('Line one\\\nLine two');
    expect(blocks[0]).toMatchObject({ type: 'paragraph', lines: ['Line one', 'Line two'] });
  });

  it('ignores blank lines', () => {
    expect(parseBlocks('\n\n  \n')).toEqual([]);
  });
});

describe('Markdown rendering', () => {
  it('renders bold as an element rather than asterisks', () => {
    // The reported bug: the preview showed the raw ** while the PDF did not.
    render(<Markdown text="Plain **bold** here" />);
    const strong = screen.getByText('bold');
    expect(strong.tagName).toBe('STRONG');
    expect(screen.queryByText(/\*\*/)).toBeNull();
  });

  it('renders italics', () => {
    render(<Markdown text="Some *emphasis* here" />);
    expect(screen.getByText('emphasis').tagName).toBe('EM');
  });

  it('renders a bullet list', () => {
    render(<Markdown text={"Intro\n- alpha\n- beta"} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('alpha')).toBeTruthy();
  });

  it('handles bold inside a list item', () => {
    render(<Markdown text="- **Led** the team" />);
    expect(screen.getByText('Led').tagName).toBe('STRONG');
  });

  it('does not treat CV text as markup', () => {
    render(<Markdown text="Reduced cost <script>alert(1)</script> by 40%" />);
    // Rendered as text, never parsed as an element.
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText(/alert\(1\)/)).toBeTruthy();
  });

  it('renders nothing for empty text', () => {
    const { container } = render(<Markdown text="" />);
    expect(container.textContent).toBe('');
  });
});

describe('paragraph separation', () => {
  it('a blank line starts a new paragraph', () => {
    // Skipping blank lines merged consecutive paragraphs into one, so the
    // preview showed a line break where the export produced two paragraphs.
    const blocks = parseBlocks('First para.\n\nSecond para.');
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toMatchObject({ type: 'paragraph', lines: ['First para.'] });
    expect(blocks[1]).toMatchObject({ type: 'paragraph', lines: ['Second para.'] });
  });

  it('a single newline stays within one paragraph', () => {
    const blocks = parseBlocks('Line one\nLine two');
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toMatchObject({ lines: ['Line one', 'Line two'] });
  });

  it('a blank line separates two lists', () => {
    const blocks = parseBlocks('- one\n\n- two');
    expect(blocks).toHaveLength(2);
  });

  it('renders separate paragraphs as separate elements', () => {
    const { container } = render(<Markdown text={'First para.\n\nSecond para.'} />);
    expect(container.querySelectorAll('p')).toHaveLength(2);
  });
});

describe('emphasis does not depend on inherited weight', () => {
  it('bold is set explicitly', () => {
    // Tailwind's preflight uses `bolder`, which computes to normal when the
    // body weight is light — so bold looked unbold in the preview.
    render(<Markdown text="Plain **bold** here" />);
    expect(screen.getByText('bold')).toHaveStyle({ fontWeight: '700' });
  });

  it('italic is set explicitly', () => {
    render(<Markdown text="Some *slanted* text" />);
    expect(screen.getByText('slanted')).toHaveStyle({ fontStyle: 'italic' });
  });
});
