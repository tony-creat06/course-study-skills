"""Small shared dollar classifier for saved teaching text.

This is a prose heuristic, not a TeX parser. An unescaped dollar followed by an
amount can be currency; explicit dollar delimiters and symbolic continuations
remain mathematical. Ambiguous single-letter continuations are treated as math.
"""
import re

_AMOUNT = re.compile(r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?')
_SYMBOL = re.compile(r'[+^=*/_\\{}<>≤≥≠≈×÷∑∫]')
_MATH_WORD = re.compile(r'(?:sin|cos|tan|cot|sec|csc|log|ln|exp|sqrt)(?=\b)', re.I)
_PROSE_JOIN = re.compile(r'(?:and|or|to|then|but|plus|each|per|for|from|at)\b', re.I)


def _escaped(text, position):
    start = position
    while start and text[start - 1] == '\\':
        start -= 1
    return (position - start) % 2 == 1


def _next_dollar(text, start):
    for position in range(start, len(text)):
        if text[position] == '\n':
            break
        if text[position] == '$' and not _escaped(text, position):
            return position
    return None


def _numeric_math_tail(value):
    # Only simple numeric/algebraic continuation is recognized; ordinary words
    # such as "then use" must not turn a price followed by math into one formula.
    value = re.sub(r'\b(?:and|or)\b', ' ', value, flags=re.I)
    has_variable = bool(re.search(r'\b[A-Za-z]\b', value))
    value = re.sub(r'\b[A-Za-z]\b', '', value)
    return bool((value.strip() or has_variable)
                and re.fullmatch(r'[\d\s.,;:!?()+^=*/_\\{}\[\]<>–—-]*', value))


def is_currency_dollar(text, position):
    """Whether this exact unescaped dollar begins a prose currency amount.

    Bare amounts, sentence punctuation, and ordinary prose after an amount are
    allowed, including successive prices. A closing dollar, mathematical
    operator, or single-letter variable keeps the expression mathematical.
    """
    if (position < 0 or position >= len(text) or text[position] != '$'
            or _escaped(text, position)
            or (position and text[position - 1] == '$')
            or text[position + 1:position + 2] == '$'):
        return False
    match = _AMOUNT.match(text, position + 1)
    if not match:
        return False
    end = match.end()
    following = text[end:end + 1]
    # Do not accept a numeric prefix of a variable, long decimal, or expression.
    if following and (following.isalnum() and not '\u3400' <= following <= '\u9fff'):
        return False
    if following == '.' and text[end + 1:end + 2].isdigit():
        return False
    if following == '$' or (following and _SYMBOL.match(following)):
        return False
    if following and not (following.isspace() or following in '.,;:!?，。；：！？、()[]—–-'
                          or '\u3400' <= following <= '\u9fff'):
        return False
    line_end = text.find('\n', end)
    if line_end < 0:
        line_end = len(text)
    tail = text[end:line_end].lstrip()
    if not tail:
        return True
    if tail[0] in '-–—':
        # A price range can be prose; a numerical subtraction is mathematical.
        return bool(re.match(r'[-–—]\s*\$\d', tail))
    if _SYMBOL.match(tail) or _MATH_WORD.match(tail):
        return False
    # In price prose, "a day" is an article followed by a noun, not a lone
    # variable. Explicit closing dollars below still keep "$2 a day$" as math.
    article_prose = re.match(r'a\s+[A-Za-z]{2,}(?=$|[\s$.,;:!?])', tail, re.I)
    if re.match(r'[A-Za-z](?=$|[\s$+^=*/_\\{}<>.,;:!?])', tail) and not article_prose:
        return False
    next_dollar = _next_dollar(text, end)
    if next_dollar is None and tail[0] in '([0123456789' and _numeric_math_tail(tail):
        return False
    if next_dollar is not None:
        between = text[end:next_dollar].strip()
        if not between:
            return False
        # A second amount is another price, not the closer of the first one.
        if _AMOUNT.match(text, next_dollar + 1):
            return True
        if _numeric_math_tail(between):
            return False
        # A final dollar is an explicit closer, even after prose-like words.
        # When another math span follows a price ("$5 and $x$"), prose can make
        # the boundary clear without swallowing the following mathematical span.
        if _next_dollar(text, next_dollar + 1) is None:
            return False
        if not (re.search(r'[.,;:!?，。；：！？、\u3400-\u9fff]', between)
                or _PROSE_JOIN.match(between)):
            return False
    return True


def has_math_dollars(text):
    """Return whether text contains an unescaped, non-currency dollar.

    Intended for renderers that require native rendered math and reject raw TeX.
    Does not skip code: the caller decides which text nodes belong to its policy.
    """
    return any(char == '$' and not _escaped(text, position)
               and not is_currency_dollar(text, position)
               for position, char in enumerate(text))
