"""LaTeX generation, where the PDF diverged from the preview.

Three faults made an exported PDF look unlike what the editor showed:
line spacing was snapped to single/onehalf/double instead of using the
configured ratio; justified text was hyphenated where CSS is not; and a CV with
no typography fell back to a static template entirely unlike the preview.
"""

import re

import pytest

from app.models.typography_models import TypographyConfig
from app.utils.latex_template_generator import generate_latex_template


def _template(line_height=None):
    config = TypographyConfig()
    if line_height is not None:
        config.body_style.line_height = line_height
    return generate_latex_template(config)


def _stretch(template):
    match = re.search(r'setstretch\{([0-9.]+)\}', template)
    return float(match.group(1)) if match else None


class TestLineSpacing:
    @pytest.mark.parametrize("line_height", [1.0, 1.2, 1.4, 1.5, 1.8, 2.0])
    def test_the_configured_ratio_is_preserved(self, line_height):
        """LaTeX's baseline at setstretch 1 is already ~1.2x the font size, so
        the stretch is the CSS ratio over 1.2. Snapping to onehalfspacing made
        a 1.4 render as 1.5."""
        stretch = _stretch(_template(line_height))
        assert stretch == pytest.approx(line_height / 1.2, abs=0.002)

    def test_distinct_heights_produce_distinct_spacing(self):
        assert _stretch(_template(1.2)) != _stretch(_template(1.4))

    def test_no_bucketed_spacing_commands_remain(self):
        template = _template(1.4)
        for command in (r'\onehalfspacing', r'\doublespacing', r'\singlespacing'):
            assert command not in template


class TestHyphenation:
    def test_hyphenation_is_disabled(self):
        """LaTeX breaks words to justify a line; CSS does not. The same
        paragraph wrapped differently in the PDF and the preview."""
        template = _template()
        assert r'\hyphenpenalty=10000' in template
        assert r'\exhyphenpenalty=10000' in template


class TestIndentation:
    def test_the_indent_is_cleared_after_the_alignment_command(self):
        """ragged2e restores the document's default indent when it sets a
        justification mode, so clearing it only in the preamble was not enough."""
        template = _template()
        body = template[template.index(r'\begin{document}'):]
        assert r'\setlength{\parindent}{0pt}' in body

    def test_the_indent_is_also_cleared_in_the_preamble(self):
        template = _template()
        preamble = template[: template.index(r'\begin{document}')]
        assert r'\setlength{\parindent}{0pt}' in preamble


class TestDefaultsAreUsable:
    def test_a_default_config_generates_a_template(self):
        """A CV created by import has no typography. The export now falls back
        to these defaults rather than a static template unlike the preview."""
        template = generate_latex_template(TypographyConfig())
        assert r'\begin{document}' in template
        assert '$body$' in template


class TestTableSupport:
    """Pandoc renders any pipe table as a longtable with booktabs rules.

    Without these packages the whole PDF build fails with "Environment
    longtable undefined" — so a CV containing a single table, or the assessment
    appendix with its score table, produced no file at all.
    """

    @pytest.mark.parametrize("package", ["longtable", "booktabs", "array", "calc"])
    def test_table_packages_are_loaded(self, package):
        assert f"usepackage{{{package}}}" in _template()


class TestBodyColour:
    """Body colour was defined in the preamble but never selected, so body text
    always rendered black however it was configured — while the preview and the
    DOCX export both honoured it."""

    def _coloured(self):
        config = TypographyConfig()
        config.body_style.color.r = 40
        config.body_style.color.g = 60
        config.body_style.color.b = 90
        return generate_latex_template(config)

    def test_the_colour_is_defined_from_the_config(self):
        assert r'\definecolor{bodycolor}{RGB}{40,60,90}' in self._coloured()

    def test_the_colour_is_actually_selected(self):
        assert r'\color{bodycolor}' in self._coloured()

    def test_it_is_selected_inside_the_document(self):
        """Selecting it in the preamble alone would have no effect on body text."""
        template = self._coloured()
        body = template[template.index(r'\begin{document}'):]
        assert r'\color{bodycolor}' in body

    def test_headings_keep_their_own_colours(self):
        template = self._coloured()
        for name in ('h1color', 'h2color', 'h3color'):
            assert f'\\color{{{name}}}' in template


class TestBullets:
    """A template's bullet character must render in the CV's text font.

    "▸" is not in Liberation Sans — xelatex logs "Missing character: There is
    no ▸ (U+25B8)" and draws an empty box, which is what every list item in an
    exported CV looked like.
    """

    def _label(self, bullet):
        config = TypographyConfig()
        config.bullet_style = bullet
        template = generate_latex_template(config)
        match = re.search(r'setlist\[itemize\]\{label=([^,]*),', template)
        return match.group(1) if match else None

    def test_the_triangle_becomes_a_maths_symbol(self):
        assert self._label('▸') == r'\ensuremath{\blacktriangleright}'

    def test_the_round_bullet_uses_textbullet(self):
        assert self._label('•') == r'\textbullet'

    def test_no_raw_high_codepoint_reaches_the_template(self):
        for bullet in ('▸', '►', '▶', '‣', '■', '○', '◦'):
            assert self._label(bullet).startswith('\\'), bullet

    def test_no_maths_dollars_reach_the_template(self):
        """This is a pandoc template: a bare $ starts a variable and breaks
        the template parser before LaTeX sees it."""
        config = TypographyConfig()
        config.bullet_style = '▸'
        assert '$' not in generate_latex_template(config).replace('$body$', '')

    def test_an_unmapped_character_is_left_alone(self):
        """It may well be in the font; silently replacing the author's choice
        would be worse than letting them see it."""
        assert self._label('~') == '~'

    def test_an_empty_bullet_falls_back(self):
        assert self._label('') == r'\textbullet'


class TestStockTemplateBullets:
    """Every shipped template must use a bullet its own fonts can draw.

    The "tech" template specified "▸" while setting Liberation faces, which do
    not contain U+25B8 — so applying it silently reintroduced a bullet that had
    to be substituted at export time and that nobody had chosen.
    """

    def test_no_template_uses_a_character_outside_its_fonts(self):
        from app.models.typography_models import TYPOGRAPHY_TEMPLATES

        # Characters the Liberation faces actually contain.
        safe = {'•', '◦', '-', '–', '*', '·'}
        for template_id, template in TYPOGRAPHY_TEMPLATES.items():
            bullet = template.typography.bullet_style
            assert bullet in safe, f"{template_id} uses {bullet!r}"

    def test_every_template_bullet_maps_to_latex(self):
        from app.models.typography_models import TYPOGRAPHY_TEMPLATES
        from app.utils.latex_template_generator import LaTeXTemplateGenerator

        for template_id, template in TYPOGRAPHY_TEMPLATES.items():
            rendered = LaTeXTemplateGenerator._latex_bullet(template.typography.bullet_style)
            assert rendered, template_id
