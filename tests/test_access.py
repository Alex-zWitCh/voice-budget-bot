from types import SimpleNamespace

from services.access import is_allowed_call, is_allowed_identity, is_allowed_message


def _config(allowed_user_ids=(), allowed_chat_ids=()):
    return SimpleNamespace(allowed_user_ids=list(allowed_user_ids), allowed_chat_ids=list(allowed_chat_ids))


def _message(user_id=10, chat_id=100, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        chat=SimpleNamespace(id=chat_id, type=chat_type),
    )


def _call(user_id=10, chat_id=100, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id, type=chat_type)),
    )


def test_private_allowed_by_default():
    assert is_allowed_message(_config(), _message()) is True


def test_group_rejected_without_allowed_chat_ids():
    assert is_allowed_message(_config(), _message(chat_type="group")) is False


def test_group_allowed_when_chat_in_list():
    config = _config(allowed_chat_ids=(100,))
    assert is_allowed_message(config, _message(chat_type="group")) is True
    assert is_allowed_message(config, _message(chat_id=200, chat_type="group")) is False


def test_allowed_user_ids_restricts():
    config = _config(allowed_user_ids=(10,))
    assert is_allowed_message(config, _message(user_id=10)) is True
    assert is_allowed_message(config, _message(user_id=11)) is False


def test_private_chat_restricted_by_allowed_chat_ids():
    config = _config(allowed_chat_ids=(100,))
    assert is_allowed_message(config, _message(chat_id=100)) is True
    assert is_allowed_message(config, _message(chat_id=200)) is False


def test_call_matches_message_semantics():
    config = _config(allowed_user_ids=(10,))
    assert is_allowed_call(config, _call()) is True
    assert is_allowed_call(config, _call(user_id=99)) is False


def test_identity_group_in_allowed_chat_but_user_not_allowed():
    config = _config(allowed_user_ids=(10,), allowed_chat_ids=(100,))
    assert is_allowed_identity(config, 10, 100, "group") is True
    assert is_allowed_identity(config, 99, 100, "group") is False
