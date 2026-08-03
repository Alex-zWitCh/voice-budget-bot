import pytest

from config import Config


def test_config_requires_keys():
    config = Config.from_env()
    empty = config.__class__(
        **{
            **config.__dict__,
            "bot_token": "",
            "groq_api_key": "",
            "deepseek_api_key": "",
        }
    )
    with pytest.raises(ValueError) as exc:
        empty.validate()
    assert "BOT_TOKEN" in str(exc.value)


def test_fallback_stt_requires_key_and_url_when_enabled():
    config = Config.from_env()
    broken = config.__class__(
        **{
            **config.__dict__,
            "fallback_stt_enabled": True,
            "fallback_stt_api_key": "",
            "fallback_stt_base_url": "",
        }
    )
    with pytest.raises(ValueError) as exc:
        broken.validate()
    assert "FALLBACK_STT_API_KEY" in str(exc.value)
    assert "FALLBACK_STT_BASE_URL" in str(exc.value)
