#!/usr/bin/env python3
"""Summarize human-checked exam records; never parse PDFs or forecast questions."""
import argparse
import importlib.util
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

UNKNOWN = '未分类'


def valid_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def topic_list(value):
    if not isinstance(value, list) or any(not isinstance(t, str) or not t.strip() for t in value):
        raise ValueError('topics must be a list of nonempty strings')
    if UNKNOWN in [t.strip() for t in value]:
        raise ValueError('Use [] for unknown topics; 未分类 is reserved')
    return sorted(set(t.strip() for t in value))


def percentages(counter, total):
    return [{'topic': name, 'question_count': count,
             'percent_of_questions': None if total == 0 else round(100 * count / total, 4)}
            for name, count in sorted(counter.items())]


def analyze_paper(paper):
    if not isinstance(paper.get('id'), str) or not paper['id'].strip():
        raise ValueError('Each paper needs a nonempty id')
    if paper.get('kind') not in ('real', 'mock', 'practice'):
        raise ValueError('kind must be real, mock or practice')
    year = paper.get('exam_year')
    if year is not None and (not isinstance(year, int) or isinstance(year, bool)):
        raise ValueError('exam_year must be the actual integer year or null')
    if not isinstance(paper.get('source'), str) or not paper['source'].strip():
        raise ValueError('Source/version is required')
    if not isinstance(paper.get('scope_complete'), bool):
        raise ValueError('scope_complete must be explicit')
    required = paper.get('all_questions_required')
    if required is not None and not isinstance(required, bool):
        raise ValueError('all_questions_required must be true/false/null')
    questions = paper.get('questions')
    if not isinstance(questions, list):
        raise ValueError('questions must be a list')
    seen = set()
    primary, coverage, abilities, mark_groups = Counter(), Counter(), Counter(), Counter()
    unknown_marks, unclassified_parts, part_count = 0, 0, 0
    for question in questions:
        number = question.get('number')
        if not isinstance(number, (str, int)) or isinstance(number, bool) or not str(number).strip():
            raise ValueError('Each question needs a number')
        identity = str(number).strip()
        if identity in seen:
            raise ValueError('Duplicate question number: ' + identity)
        seen.add(identity)
        main_topic = question.get('primary_topic')
        if main_topic is not None and (not isinstance(main_topic, str) or not main_topic.strip() or main_topic.strip() == UNKNOWN):
            raise ValueError('primary_topic must be nonempty text or null')
        primary[main_topic.strip() if main_topic else UNKNOWN] += 1
        parts = question.get('parts')
        if not isinstance(parts, list) or not parts:
            raise ValueError('Represent at least one part, even if marks/topics are unknown')
        part_ids, question_topics, question_abilities = set(), set(), set()
        for part in parts:
            label = part.get('label')
            if not isinstance(label, str) or not label.strip() or label in part_ids:
                raise ValueError('Part labels must be nonempty and unique within a question')
            part_ids.add(label)
            page = part.get('source_page')
            if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
                raise ValueError('source_page must be a one-based PDF page or null')
            topics = topic_list(part.get('topics'))
            question_topics.update(topics)
            question_abilities.update(topic_list(part.get('abilities', [])))
            part_count += 1
            unclassified_parts += not bool(topics)
            marks = part.get('marks')
            if marks is None:
                unknown_marks += 1
            elif not valid_number(marks):
                raise ValueError('marks must be a nonnegative finite number or null')
            else:
                # One part is one allocation. Multiple topics form one joint group.
                mark_groups[tuple(topics) if topics else (UNKNOWN,)] += marks
        coverage.update(question_topics or {UNKNOWN})
        abilities.update(question_abilities)
    known_marks = sum(mark_groups.values())
    expected = paper.get('expected_available_marks')
    if expected is not None and not valid_number(expected):
        raise ValueError('expected_available_marks must be nonnegative or null')
    check = 'not_checked'
    if expected is not None and paper['scope_complete'] and unknown_marks == 0:
        if not math.isclose(known_marks, expected, abs_tol=1e-8):
            raise ValueError('Complete paper available-mark total disagrees with expected_available_marks')
        check = 'matched'
    count = len(questions)
    if sum(primary.values()) != count:
        raise AssertionError('Primary-topic denominator mismatch')
    return {'question_count': count, 'part_count': part_count,
            'primary_topics': percentages(primary, count),
            'topic_coverage': percentages(coverage, count),
            'ability_coverage': percentages(abilities, count),
            'coverage_overlaps': True,
            'known_available_marks': known_marks, 'unknown_mark_parts': unknown_marks,
            'unclassified_parts': unclassified_parts,
            'mark_groups': [{'topics': list(group), 'marks': marks}
                            for group, marks in sorted(mark_groups.items())],
            'available_mark_total_check': check,
            'candidate_required_marks': known_marks if required is True and paper['scope_complete'] and not unknown_marks else None,
            'scope_note': '完整已声明范围' if paper['scope_complete'] else '部分试卷，不能据此声称全卷覆盖',
            'marks_note': '联合组只计一次；未知分值未当作0；可见分值不自动等于考生必答总分'}


def summarize(data):
    papers = data.get('papers')
    if not isinstance(papers, list) or not papers:
        raise ValueError('papers must be a nonempty list')
    seen, results, groups = set(), [], defaultdict(list)
    for paper in papers:
        analysis = analyze_paper(paper)
        if paper['id'] in seen:
            raise ValueError('Duplicate paper id: ' + paper['id'])
        seen.add(paper['id'])
        results.append(dict(paper, analysis=analysis))
        groups[(paper.get('exam_year'), paper['kind'])].append(results[-1])
    years = []
    for (year, kind), entries in sorted(groups.items(), key=lambda pair: (str(pair[0][0]), pair[0][1])):
        primary, coverage, abilities = Counter(), Counter(), Counter()
        for entry in entries:
            for field, counter in [('primary_topics', primary), ('topic_coverage', coverage), ('ability_coverage', abilities)]:
                counter.update({row['topic']: row['question_count'] for row in entry['analysis'][field]})
        total = sum(entry['analysis']['question_count'] for entry in entries)
        years.append({'exam_year': year, 'kind': kind, 'paper_ids': [e['id'] for e in entries],
                      'all_declared_scopes_complete': all(e['scope_complete'] for e in entries),
                      'question_count': total, 'primary_topics': percentages(primary, total),
                      'topic_coverage': percentages(coverage, total), 'ability_coverage': percentages(abilities, total)})
    return {'papers': results, 'year_groups': years,
            'method': 'Primary topic: one big question once, unknown included. Coverage: each question/topic pair once, overlaps allowed. Marks: one allocation per part/joint group. Real/mock/practice separated.',
            'limitations': ['Input labels and source completeness require human/agent review.',
                            'Historical frequency is not an exam probability or future guarantee.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', help='Scratch output outside shared course records')
    parser.add_argument('--root', help='Shared course root for version-checked output')
    parser.add_argument('--path', help='Course-relative output path')
    parser.add_argument('--expected', help='SHA from course_records.py read, or absent')
    args = parser.parse_args()
    try:
        protected = args.root is not None
        if protected:
            if args.output or args.path is None or args.expected is None:
                raise ValueError('Protected output requires --root --path --expected and no --output')
            destination = Path(args.root) / args.path
        else:
            if not args.output or args.path is not None or args.expected is not None:
                raise ValueError('Use --output for scratch output, or the full protected-output options')
            destination = Path(args.output)
        source = Path(args.input)
        if source.resolve() == destination.resolve():
            raise ValueError('Output must not overwrite the source records')
        result = summarize(json.loads(source.read_text(encoding='utf-8')))
        content = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if protected:
            module_path = Path(__file__).resolve().parents[2] / 'study-planner/scripts/course_records.py'
            spec = importlib.util.spec_from_file_location('course_records', module_path)
            records = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(records)
            saved = records.write_record(args.root, args.path, 'analyst', args.expected, content)
            print(json.dumps(dict(saved, papers=len(result['papers'])), ensure_ascii=False))
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding='utf-8')
        print(json.dumps({'papers': len(result['papers']), 'output': str(destination)}, ensure_ascii=False))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
