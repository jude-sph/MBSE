from src.llm_client import _extract_json


def test_extract_json_from_code_block():
    text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
    assert _extract_json(text) == '{"key": "value"}'


def test_extract_json_plain():
    text = '{"key": "value"}'
    assert _extract_json(text) == '{"key": "value"}'


def test_extract_json_from_generic_code_block():
    text = '```\n{"key": "value"}\n```'
    assert _extract_json(text) == '{"key": "value"}'
