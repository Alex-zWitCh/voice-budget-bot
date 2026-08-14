import pytest

from config import Config


def test_config_requires_keys():
    config = Config.from_env()
    empty = config.__class__(
        **{
            **config.__dict__,
            "bot_token": "",
            "stt_api_key": "",
            "deepseek_api_key": "",
        }
    )
    with pytest.raises(ValueError) as exc:
        empty.validate()
    assert "BOT_TOKEN" in str(exc.value)


def test_groq_fallback_requires_key_when_enabled():
    config = Config.from_env()
    broken = config.__class__(
        **{
            **config.__dict__,
            "groq_fallback_enabled": True,
            "groq_api_key": "",
        }
    )
    with pytest.raises(ValueError) as exc:
        broken.validate()
    assert "GROQ_API_KEY" in str(exc.value)
