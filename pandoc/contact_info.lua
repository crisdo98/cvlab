-- Route the contact-info div to the right representation per output format.
--
-- The export service emits the contact line once, as:
--   ::: {.contact-info custom-style="Subtitle"}
--   email | phone | location | LinkedIn
--   :::
--
-- LaTeX needs the styled \contactinfo macro; DOCX uses the custom-style
-- attribute Pandoc already understands; every other writer (plain text
-- included) renders the paragraph as-is.

local function has_class(div, name)
  for _, class in ipairs(div.classes) do
    if class == name then return true end
  end
  return false
end

function Div(div)
  if not has_class(div, 'contact-info') then
    return nil
  end

  if FORMAT:match('latex') or FORMAT:match('beamer') then
    local text = pandoc.utils.stringify(div)
    return pandoc.RawBlock('latex', '\\contactinfo{' .. text .. '}')
  end

  -- DOCX keeps the div so custom-style="Subtitle" is applied;
  -- all other writers fall through to the plain paragraph
  return nil
end
