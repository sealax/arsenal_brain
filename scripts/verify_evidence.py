"""Check exported call/result correlation and citations against the actual corpus.

This validates recorded mechanics, not human authorship or semantic correctness.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'api'))
from app.knowledge import DEFAULT_CORPUS, KnowledgeIndex


def verify(evidence: dict):
    index = KnowledgeIndex()
    if evidence['working_tree_dirty']:
        raise ValueError('Recorded source tree was dirty')
    if evidence['corpus_sha256'] != index.corpus_sha256:
        raise ValueError('Corpus fingerprint changed')
    calls, logs = evidence['client_calls'], evidence['server_events']
    if not calls or not logs or not evidence['final_answer'].strip():
        raise ValueError('Missing client call, server result or final answer')
    known_ids = set()
    for call in calls:
        if call['server'] != 'arsenal' or call['tool'] != 'search_arsenal_knowledge':
            raise ValueError('Unexpected tool')
        if call['status'] != 'completed' or call['error']:
            raise ValueError('Tool call failed')
        args = call['arguments']
        if isinstance(args, str):
            args = json.loads(args)
        structured = call['result']['structured_content']
        if not any(log['arguments']['question'] == args['question'] and
                   log['arguments']['top_k'] == args.get('top_k', 3) and
                   log['result'] == structured for log in logs):
            raise ValueError('Client/server result mismatch')
        if structured['corpus_sha256'] != index.corpus_sha256:
            raise ValueError('Tool result corpus changed')
        for source in structured['sources']:
            name = source['document']
            if Path(name).name != name:
                raise ValueError('Invalid document path')
            raw = (DEFAULT_CORPUS / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != source['document_sha256']:
                raise ValueError('Document fingerprint changed')
            if raw.decode('utf-8')[source['char_start']:source['char_end']] != source['text']:
                raise ValueError('Source span mismatch')
            if source['source_id'] != f"{name}:{source['char_start']}-{source['char_end']}":
                raise ValueError('Source ID mismatch')
            known_ids.add(source['source_id'])
    # The answerable case must use an actual returned citation.
    if evidence['case'] == 'founding' and not any(s in evidence['final_answer'] for s in known_ids):
        raise ValueError('No returned source cited in founding answer')
    return {'case': evidence['case'], 'verified_calls': len(calls),
            'verified_source_ids': sorted(known_ids), 'result': 'mechanics_verified'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', type=Path, nargs='+')
    args = parser.parse_args()
    for path in args.files:
        print(json.dumps(verify(json.loads(path.read_text()))))
