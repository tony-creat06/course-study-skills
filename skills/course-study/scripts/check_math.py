#!/usr/bin/env python3
"""Flag common mathematical Markdown mistakes without changing the source.

This is a small text check, not a TeX parser, renderer, or correctness proof.
Code spans/fences are excluded. Ambiguous plain-text commands are warnings.
"""
import argparse
import json
from pathlib import Path
import re

TOKENS = re.compile(r'(?<!\\)\$\$|(?<!\\)\$|(?<!\\)\\[()[\]]')
BARE_COMMAND = re.compile(r'(?<![\\\w])(?:mathrm|mathbf|mathit|mathbb|mathcal|operatorname|frac|sqrt)\s*\{')
PLAIN_TEX = re.compile(r'\\(?:frac|sqrt|partial|hbar|psi|omega|lambda|alpha|beta|sum|int|mathrm|mathbf|operatorname)\b')


def blank(value):
    return ''.join('\n' if c == '\n' else ' ' for c in value)


def mask_code(source):
    lines, fence = [], None
    for line in source.splitlines(keepends=True):
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if fence:
            lines.append(blank(line))
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence):
                fence = None
        elif match:
            fence = match[1]
            lines.append(blank(line))
        else:
            lines.append(line)
    return re.sub(r'(`+)([^\n]*?)\1', lambda m: blank(m[0]), ''.join(lines))


def check(source):
    text, issues, spans = mask_code(source), [], []

    def report(position, kind, message, severity='error'):
        line = text.count('\n', 0, position) + 1
        column = position - text.rfind('\n', 0, position)
        issues.append({'line': line, 'column': column, 'kind': kind,
                       'severity': severity, 'message': message})

    active = None
    closing = {'$': '$', '$$': '$$', r'\(': r'\)', r'\[': r'\]'}
    for token in TOKENS.finditer(text):
        value = token[0]
        if active:
            start, opener, content_start = active
            if value == closing[opener]:
                spans.append((start, token.end()))
                body = text[content_start:token.start()]
                for bare in BARE_COMMAND.finditer(body):
                    report(content_start + bare.start(), 'missing-backslash',
                           'Possible missing backslash before a TeX command; check the original formula.')
                braces = []
                for brace in re.finditer(r'(?<!\\)[{}]', body):
                    if brace[0] == '{':
                        braces.append(brace.start())
                    elif braces:
                        braces.pop()
                    else:
                        report(content_start + brace.start(), 'unbalanced-brace', 'Unmatched closing math brace.')
                for position in braces:
                    report(content_start + position, 'unbalanced-brace', 'Unclosed math brace.')
                active = None
            elif value in {r'\)', r'\]'}:
                report(token.start(), 'delimiter', 'Math closing delimiter does not match its opening delimiter.')
        elif value in closing:
            rest = text[token.end():].split('\n', 1)[0]
            # A recorded, line-leading suite invocation is command text.
            line_start = text.rfind('\n', 0, token.start()) + 1
            if value == '$' and not text[line_start:token.start()].strip() and re.match(
                    r'(?:study-planner|course-study|exam-analysis|practice-builder)(?=\s|$)', rest):
                continue
            # A lone price such as $20 is prose, not an unfinished math expression.
            if value == '$' and re.match(r'\d', rest) and '$' not in rest and not PLAIN_TEX.search(rest):
                continue
            active = (token.start(), value, token.end())
        else:
            report(token.start(), 'delimiter', 'Math closing delimiter has no opening delimiter.')
    if active:
        report(active[0], 'delimiter', 'Unclosed math delimiter.')
        spans.append((active[0], len(text)))
    outside = list(text)
    for start, end in spans:
        outside[start:end] = blank(text[start:end])
    for command in PLAIN_TEX.finditer(''.join(outside)):
        report(command.start(), 'outside-math', 'TeX command outside a math delimiter; inspect presentation.', 'warning')
    return sorted(issues, key=lambda x: (x['line'], x['column']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', help='UTF-8 Markdown notes or saved draft replies')
    args = parser.parse_args()
    results, failed = [], False
    for filename in args.files:
        try:
            issues = check(Path(filename).read_text(encoding='utf-8'))
            failed |= any(issue['severity'] == 'error' for issue in issues)
            results.append({'path': filename, 'issues': issues})
        except (OSError, UnicodeError) as exc:
            failed = True
            results.append({'path': filename, 'read_error': str(exc)})
    print(json.dumps({'files': results, 'scope': 'text syntax only; inspect warnings; no source changes'}, ensure_ascii=False, indent=2))
    raise SystemExit(2 if failed else 0)


if __name__ == '__main__':
    main()
