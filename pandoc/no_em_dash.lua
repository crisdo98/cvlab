-- Pandoc Lua filter to replace Unicode em/en dashes with ASCII hyphen-minus
-- Applies to all string content nodes

local function replace_dashes(s)
  return s:gsub("\226\128\148", "-") -- em dash U+2014
           :gsub("\226\128\147", "-") -- en dash U+2013
end

return {
  Str = function(el)
    el.text = replace_dashes(el.text)
    return el
  end,
  Space = function(el)
    return el
  end,
  -- Also handle Code, Link titles, etc.
  Code = function(el)
    el.text = replace_dashes(el.text)
    return el
  end,
  Link = function(el)
    if el.title then el.title = replace_dashes(el.title) end
    return el
  end,
  Emph = function(el)
    for i, c in ipairs(el.content) do
      if c.t == 'Str' then c.text = replace_dashes(c.text) end
    end
    return el
  end,
}
