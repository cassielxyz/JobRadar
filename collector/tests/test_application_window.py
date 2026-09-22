from datetime import date, timedelta
from jobradar.application_window import application_is_expired, infer_closing_date


def test_registration_range_uses_closing_date():
    text = (
        'The link for the application for on-line registration will be hosted during the period '
        'from 27.06.2026 (10:00 AM) to 20.07.2026 (11.55 PM).'
    )
    assert infer_closing_date(text) == '2026-07-20'


def test_last_date_for_receipt_is_detected():
    text = 'LAST DATE FOR RECEIPT OF ON-LINE APPLICATIONS IS 20.07.2026'
    assert infer_closing_date(text) == '2026-07-20'


def test_past_deadline_is_expired():
    past = (date.today() - timedelta(days=1)).isoformat()
    assert application_is_expired(past, '')
