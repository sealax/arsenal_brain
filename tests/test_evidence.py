import copy
import importlib.util
from pathlib import Path

import pytest
from app.knowledge import KnowledgeIndex

path = Path(__file__).resolve().parents[1] / 'scripts' / 'verify_evidence.py'
spec = importlib.util.spec_from_file_location('verify_evidence', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample():
    result = KnowledgeIndex().search('When was Arsenal founded?').model_dump()
    arguments = {'question': result['question'], 'top_k': 3}
    return {'working_tree_dirty': False, 'corpus_sha256': result['corpus_sha256'],
            'case': 'founding', 'final_answer': '1886 ' + result['sources'][0]['source_id'],
            'client_calls': [{'server': 'arsenal', 'tool': 'search_arsenal_knowledge',
                              'status': 'completed', 'error': None, 'arguments': arguments,
                              'result': {'structured_content': copy.deepcopy(result)}}],
            'server_events': [{'arguments': arguments, 'result': result}]}


def test_valid_recorded_mechanics():
    assert module.verify(sample())['verified_calls'] == 1


def test_tampered_client_result_is_rejected():
    evidence = sample()
    evidence['client_calls'][0]['result']['structured_content']['sources'][0]['text'] = 'invented'
    with pytest.raises(ValueError, match='mismatch'):
        module.verify(evidence)


def test_missing_agent_call_is_not_proof():
    evidence = sample()
    evidence['client_calls'] = []
    with pytest.raises(ValueError, match='Missing'):
        module.verify(evidence)
