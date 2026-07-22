from config import Config
from welcome import AUTHOR_GITHUB_URL, welcome_text


def test_welcome_always_contains_fork_author_link():
    base_config = Config.from_env()
    config = base_config.__class__(
        **{
            **base_config.__dict__,
            "welcome_footer": "",
        }
    )

    text = welcome_text(config)

    assert AUTHOR_GITHUB_URL in text
