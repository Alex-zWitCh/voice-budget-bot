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

