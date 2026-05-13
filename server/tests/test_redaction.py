from app.services.redaction import redact


def test_redact_removes_person_name():
    result = redact("Hi, my name is John Smith and I live in Boston.")
    assert "John Smith" not in result
    assert "[REDACTED]" in result


def test_redact_removes_phone_number():
    result = redact("Call me at 555-867-5309.")
    assert "555-867-5309" not in result
    assert "[REDACTED]" in result


def test_redact_removes_email():
    result = redact("Reach me at jane.doe@example.com anytime.")
    assert "jane.doe@example.com" not in result
    assert "[REDACTED]" in result


def test_redact_returns_string():
    result = redact("Hello world.")
    assert isinstance(result, str)
