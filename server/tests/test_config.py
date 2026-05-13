def test_settings_has_required_fields():
    from app.config import get_settings
    settings = get_settings()
    assert settings.database_url.startswith("postgresql://")
    assert len(settings.encryption_key) >= 32
    assert settings.openai_api_key
    assert settings.anthropic_api_key
    assert settings.twilio_account_sid.startswith("AC")
    assert settings.twilio_auth_token
