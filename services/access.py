from config import Config


def is_allowed_identity(config: Config, user_id: int, chat_id: int, chat_type: str) -> bool:
    """Единая проверка доступа: приватные чаты или явно разрешённые группы.

    - если задан `allowed_user_ids`, пользователь обязан быть в списке;
    - в групповом/супергрупповом чате разрешён только явный `allowed_chat_ids`;
    - если задан `allowed_chat_ids`, приватный чат должен быть в списке;
    - иначе разрешены личные чаты.
    """
    if config.allowed_user_ids and user_id not in config.allowed_user_ids:
        return False
    if chat_type in {"group", "supergroup"}:
        return chat_id in config.allowed_chat_ids
    if config.allowed_chat_ids:
        return chat_id in config.allowed_chat_ids
    return chat_type == "private"


def is_allowed_message(config: Config, message) -> bool:
    user_id = message.from_user.id if message.from_user else 0
    return is_allowed_identity(config, user_id, message.chat.id, message.chat.type)


def is_allowed_call(config: Config, call) -> bool:
    user_id = call.from_user.id if call.from_user else 0
    chat = call.message.chat if call.message else None
    chat_id = chat.id if chat else 0
    chat_type = chat.type if chat else "private"
    return is_allowed_identity(config, user_id, chat_id, chat_type)
