from jobradar.ai.review import _extract_json, _result, merge_ai_score
from jobradar.models import Category


def category(fresher_only=False):
    return Category(id='c',name='C',slug='c',type='custom',role_keywords=[],hidden_keywords=[],exclude_keywords=[],locations=[],fresher_only=fresher_only)


def test_extract_json_fenced():
    obj = _extract_json('```json\n{"relevant":true,"confidence":91}\n```')
    assert obj['relevant'] is True
    assert obj['confidence'] == 91


def test_result_sanitizes():
    r = _result('gemini', {'relevant': True, 'fresher_compatible': True, 'role_family': 'networking', 'confidence': 140, 'reason': 'ok'})
    assert r.available is True
    assert r.confidence == 100


def test_merge_agree_positive():
    review = {'consensus': {'relevant': True, 'agreement': True, 'confidence': 90, 'fresher_compatible': True, 'providers': ['gemini', 'copilot']}}
    score, reasons, eligible = merge_ai_score(70, [], True, review, category(False))
    assert score == 78
    assert eligible is True
    assert reasons


def test_ai_experience_blocks_only_fresher_category():
    review = {'consensus': {'relevant': True, 'agreement': True, 'confidence': 92, 'fresher_compatible': False, 'providers': ['gemini', 'copilot']}}
    score, reasons, eligible = merge_ai_score(75, [], True, review, category(True))
    assert score == 63
    assert eligible is False
    assert any('fresher-only' in x for x in reasons)


def test_ai_experience_is_only_penalty_for_general_category():
    review = {'consensus': {'relevant': True, 'agreement': True, 'confidence': 92, 'fresher_compatible': False, 'providers': ['gemini', 'copilot']}}
    score, reasons, eligible = merge_ai_score(75, [], True, review, category(False))
    assert score == 63
    assert eligible is True
    assert any('preferred target' in x for x in reasons)
