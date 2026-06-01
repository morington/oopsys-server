import uuid

from aiogram import Bot

from oopsys_bot.registry import BotEntry, BotRegistry
from oopsys_server.application.bot_notify import merge_notify_kinds
from oopsys_server.domain.enums import BotStatus
from oopsys_server.infrastructure.security import TokenCipher


def _registry() -> BotRegistry:
    return BotRegistry(cipher=TokenCipher("test-key-for-bot-registry-unit-tests"))


def test_shared_token_delivers_to_each_account() -> None:
    registry = _registry()
    token = "123456:shared-token"
    account_a = uuid.uuid4()
    account_b = uuid.uuid4()
    registry.clients[token] = Bot(token=token)
    settings = merge_notify_kinds({})
    registry.entries[uuid.uuid4()] = BotEntry(
        db_id=uuid.uuid4(),
        account_id=account_a,
        token=token,
        chat_id="111",
        status=BotStatus.LINKED,
        notify_kinds=settings,
    )
    registry.entries[uuid.uuid4()] = BotEntry(
        db_id=uuid.uuid4(),
        account_id=account_b,
        token=token,
        chat_id="222",
        status=BotStatus.LINKED,
        notify_kinds=settings,
    )

    a_entries = registry.entries_for_account(account_a)
    b_entries = registry.entries_for_account(account_b)

    assert len(a_entries) == 1
    assert len(b_entries) == 1
    assert a_entries[0].chat_id == "111"
    assert b_entries[0].chat_id == "222"
    assert registry.client_for(token) is registry.clients[token]


def test_pending_token_is_shared_across_accounts() -> None:
    registry = _registry()
    token = "123456:shared-token"
    registry.clients[token] = Bot(token=token)
    registry.entries[uuid.uuid4()] = BotEntry(
        db_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        token=token,
        chat_id=None,
        status=BotStatus.PENDING,
        notify_kinds=merge_notify_kinds({}),
    )
    registry.entries[uuid.uuid4()] = BotEntry(
        db_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        token=token,
        chat_id="999",
        status=BotStatus.LINKED,
        notify_kinds=merge_notify_kinds({}),
    )

    assert registry.pending_tokens() == frozenset({token})
    assert len(registry.bots_for_polling()) == 1
