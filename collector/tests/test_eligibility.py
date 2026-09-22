from jobradar.eligibility import qualification_gate
from jobradar.models import Job


def candidate():
    return {
        'resume': {
            'education': ['B.E. Computer Science and Engineering'],
            'raw_text': 'B.E CSE, CCNA',
        }
    }


def job(title, description):
    return Job(
        title=title,
        company='Government employer',
        location='Bengaluru',
        description=description,
        source_id='gov',
        source_url='https://example.gov.test',
        canonical_url='https://example.gov.test/notice',
    )


def test_be_cse_does_not_satisfy_explicit_bsc_cs_requirement():
    result = qualification_gate(
        job(
            'Scientific Assistant - Computer Science',
            'Essential minimum qualification: First Class B.Sc. with Computer Science as main subject.',
        ),
        candidate(),
        strict=True,
    )
    assert result['status'] == 'ineligible'
    assert 'B.Sc' in result['reasons'][0]
    assert 'B.E/B.Tech' in result['reasons'][0]


def test_be_cse_matches_explicit_be_btech_cse_requirement():
    result = qualification_gate(
        job(
            'Scientist Engineer SC - Computer Science',
            'Essential qualification: First Class B.E./B.Tech in Computer Science or Information Technology.',
        ),
        candidate(),
        strict=True,
    )
    assert result['status'] == 'eligible'


def test_related_field_does_not_override_wrong_degree_type():
    result = qualification_gate(
        job(
            'Technical Assistant - Computer Science',
            'Essential qualification: First Class Diploma in Computer Science Engineering.',
        ),
        candidate(),
        strict=True,
    )
    assert result['status'] == 'ineligible'


def test_equivalent_wording_requires_manual_verification_when_exact_degree_differs():
    result = qualification_gate(
        job(
            'Scientific Assistant - Computer Science',
            'Essential qualification: B.Sc Computer Science or equivalent qualification.',
        ),
        candidate(),
        strict=True,
    )
    assert result['status'] == 'unknown'
