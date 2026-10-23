import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.knowledge import DEFAULT_CORPUS, KnowledgeIndex, SearchInput, chunk_spans


@pytest.fixture
def index():
    return KnowledgeIndex()


@pytest.mark.parametrize('question,expected', [
    ('What was Arsenal originally called?', 'Dial Square'),
    ('When was Arsenal founded?', '1886'),
    ('When did Arsenal move to Emirates Stadium?', '2006'),
    ('What does Victoria Concordia Crescit mean?', 'Victory Through Harmony'),
    ('Who introduced the WM formation?', 'Herbert Chapman'),
    ('How many FA Cups did Wenger win?', 'seven FA Cups'),
    ('What was the Invincibles unbeaten league run?', '49 games'),
])
def test_retrieval_finds_expected_evidence(index, question, expected):
    result = index.search(question)
    assert result.status == 'matches'
    assert expected in ' '.join(s.text for s in result.sources)


def test_unknown_question_abstention_signal(index):
    result = index.search('Who is the current captain in 2026?')
    assert result.status == 'no_match'
    assert result.sources == []


def test_matching_words_do_not_guarantee_answer(index):
    result = index.search('What is the Emirates Stadium WiFi password?')
    assert result.status == 'matches'
    assert 'not prove answerability' in result.guidance
    assert not any('password' in s.text.lower() for s in result.sources)


def test_sources_are_exact_and_fingerprinted(index):
    for source in index.search('When did Arsenal move to Emirates Stadium?', 5).sources:
        path = DEFAULT_CORPUS / source.document
        assert source.text == path.read_text()[source.char_start:source.char_end]
        assert source.document_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('value', [0, 6, -1, '3', True])
def test_top_k_rejects_invalid_and_coerced_values(index, value):
    with pytest.raises(ValidationError):
        index.search('When was Arsenal founded?', value)


@pytest.mark.parametrize('question', ['', '  ', 'ab', 'x' * 501, None, 123])
def test_invalid_question_is_rejected(index, question):
    with pytest.raises(ValidationError):
        index.search(question)


def test_no_arbitrary_extra_fields():
    with pytest.raises(ValidationError):
        SearchInput(question='Arsenal history', path='/etc/passwd')


def test_deterministic_and_bounded(index):
    first = index.search('When was Arsenal founded?', 1)
    assert len(first.sources) == 1
    assert first == index.search('When was Arsenal founded?', 1)


def test_missing_and_empty_corpus(tmp_path):
    with pytest.raises(ValueError):
        KnowledgeIndex(tmp_path)
    (tmp_path / 'empty.txt').write_text('  ')
    with pytest.raises(ValueError):
        KnowledgeIndex(tmp_path)


def test_symlink_is_rejected(tmp_path):
    (tmp_path / 'escape.txt').symlink_to(DEFAULT_CORPUS / 'arsenal_history.txt')
    with pytest.raises(ValueError, match='regular'):
        KnowledgeIndex(tmp_path)


def test_oversized_corpus_is_rejected(tmp_path):
    (tmp_path / 'large.txt').write_bytes(b'x' * 2_000_001)
    with pytest.raises(ValueError, match='byte limit'):
        KnowledgeIndex(tmp_path)


def test_spans_handle_long_unbroken_text():
    text = 'x' * 2000
    spans = list(chunk_spans(text))
    assert ''.join(text[start:end] for start, end in spans) == text
    assert all(0 < end - start <= 850 for start, end in spans)


def test_overlap_preserves_context_without_losing_source_text():
    text = ('a word ' * 300).strip()
    spans = list(chunk_spans(text))
    assert spans[1][0] < spans[0][1]
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    assert all(next_start <= end + 1 for (_, end), (next_start, _) in zip(spans, spans[1:]))
