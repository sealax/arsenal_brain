"""Ten retrieval cases, distinct from live-model agent evaluations."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'api'))
from app.knowledge import KnowledgeIndex

CASES = [
    ('original_name', 'What was Arsenal originally called?', 'Dial Square'),
    ('foundation', 'When was Arsenal founded?', '1886'),
    ('stadium', 'When did Arsenal move to Emirates Stadium?', '2006'),
    ('motto', 'What does Victoria Concordia Crescit mean?', 'Victory Through Harmony'),
    ('chapman', 'Who introduced the WM formation?', 'Herbert Chapman'),
    ('wenger', 'How many FA Cups did Wenger win?', 'seven FA Cups'),
    ('invincibles', 'What was the Invincibles unbeaten league run?', '49 games'),
    ('missing', 'Who is the current captain in 2026?', None),
    ('other_sport', 'What is the latest NBA score?', None),
    ('unknown_overlap', 'What is the Emirates Stadium WiFi password?', 'UNSUPPORTED_MATCH'),
]


def evaluate():
    index = KnowledgeIndex()
    rows = []
    for name, question, expected in CASES:
        result = index.search(question)
        if expected == 'UNSUPPORTED_MATCH':
            passed = result.status == 'matches' and 'not prove answerability' in result.guidance
            assertion = 'Overlapping context carries a warning; this does NOT prove model abstention.'
        elif expected is None:
            passed = result.status == 'no_match' and not result.sources
            assertion = 'No match, no sources.'
        else:
            passed = expected in ' '.join(s.text for s in result.sources)
            assertion = 'Expected evidence appears in top 3 passages; not answer-generation scoring.'
        rows.append({'case': name, 'question': question, 'expected': expected,
                     'assertion': assertion, 'passed': passed,
                     'source_ids': [s.source_id for s in result.sources]})
    return {'evaluation_type': 'deterministic_retrieval', 'backend': 'local_lexical',
            'corpus_sha256': index.corpus_sha256, 'total': len(rows),
            'passed': sum(r['passed'] for r in rows), 'cases': rows}


if __name__ == '__main__':
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report['passed'] == report['total'] else 1)
