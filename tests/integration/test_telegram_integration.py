"""
Integration tests — Telegram bot command handling and orchestrator interaction.

Tests authorization, command routing, and orchestrator state transitions
through the Telegram bot interface using mocked aiogram Message objects.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.orchestrator.bot_orchestrator import BotState
from bot.telegram.bot import TelegramBot

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_message(chat_id: int = 12345, text: str = "/start") -> MagicMock:
    """Create a mocked aiogram Message."""
    message = MagicMock()
    message.chat.id = chat_id
    message.from_user = MagicMock()
    message.from_user.id = 99999
    message.text = text
    message.answer = AsyncMock()
    return message


def _make_mock_orchestrator(
    state: BotState = BotState.STOPPED,
    symbol: str = "BTCUSDT",
    strategy: str = "grid",
) -> MagicMock:
    """Create a mocked BotOrchestrator."""
    orch = MagicMock()
    orch.state = state
    orch.config = MagicMock()
    orch.config.symbol = symbol
    orch.config.strategy = strategy
    orch.start = AsyncMock()
    orch.stop = AsyncMock()
    orch.pause = AsyncMock()
    orch.resume = AsyncMock()
    orch.get_status = MagicMock(
        return_value={
            "state": state.value,
            "symbol": symbol,
            "strategy": strategy,
            "active_positions": 0,
            "total_trades": 5,
            "total_pnl": "250.00",
        }
    )
    return orch


@pytest.fixture
def bot() -> TelegramBot:
    """Create a TelegramBot with mocked dependencies."""
    orch = _make_mock_orchestrator()
    with patch("bot.telegram.bot.Bot"):
        return TelegramBot(
            token="fake-token",
            allowed_chat_ids=[12345],
            orchestrators={"test-bot": orch},
        )


@pytest.fixture
def multi_bot() -> TelegramBot:
    """Create a TelegramBot with multiple orchestrators."""
    orchestrators = {
        "grid-bot": _make_mock_orchestrator(strategy="grid"),
        "smc-bot": _make_mock_orchestrator(strategy="smc"),
        "dca-bot": _make_mock_orchestrator(strategy="dca"),
    }
    with patch("bot.telegram.bot.Bot"):
        return TelegramBot(
            token="fake-token",
            allowed_chat_ids=[12345, 67890],
            orchestrators=orchestrators,
        )


# ===========================================================================
# Authorization Tests
# ===========================================================================


class TestAuthorization:
    def test_authorized_user(self, bot):
        msg = _make_mock_message(chat_id=12345)
        assert bot._check_auth(msg) is True

    def test_unauthorized_user(self, bot):
        msg = _make_mock_message(chat_id=99999)
        assert bot._check_auth(msg) is False

    def test_no_user_info(self, bot):
        msg = _make_mock_message()
        msg.from_user = None
        assert bot._check_auth(msg) is False

    def test_multiple_allowed_chats(self, multi_bot):
        msg1 = _make_mock_message(chat_id=12345)
        msg2 = _make_mock_message(chat_id=67890)
        msg3 = _make_mock_message(chat_id=11111)
        assert multi_bot._check_auth(msg1) is True
        assert multi_bot._check_auth(msg2) is True
        assert multi_bot._check_auth(msg3) is False


# ===========================================================================
# Command Tests — /start, /help
# ===========================================================================


class TestStartHelpCommands:
    async def test_start_authorized(self, bot):
        msg = _make_mock_message(chat_id=12345)
        await bot._cmd_start(msg)
        msg.answer.assert_called_once()
        response = msg.answer.call_args[0][0]
        assert "TRADERAGENT" in response

    async def test_start_unauthorized(self, bot):
        msg = _make_mock_message(chat_id=99999)
        await bot._cmd_start(msg)
        msg.answer.assert_called_once()
        response = msg.answer.call_args[0][0]
        assert "Unauthorized" in response

    async def test_help_calls_start(self, bot):
        msg = _make_mock_message(chat_id=12345)
        await bot._cmd_help(msg)
        msg.answer.assert_called_once()


# ===========================================================================
# Command Tests — /list
# ===========================================================================


class TestListCommand:
    async def test_list_bots(self, multi_bot):
        msg = _make_mock_message(chat_id=12345)
        await multi_bot._cmd_list(msg)
        msg.answer.assert_called_once()
        response = msg.answer.call_args[0][0]
        assert "grid-bot" in response
        assert "smc-bot" in response
        assert "dca-bot" in response

    async def test_list_empty(self):
        with patch("bot.telegram.bot.Bot"):
            empty_bot = TelegramBot(token="fake", allowed_chat_ids=[12345], orchestrators={})
        msg = _make_mock_message(chat_id=12345)
        await empty_bot._cmd_list(msg)
        msg.answer.assert_called_once()
        response = msg.answer.call_args[0][0]
        assert "No bots" in response


# ===========================================================================
# Initialization Tests
# ===========================================================================


class TestBotInitialization:
    def test_initialization_with_orchestrators(self, bot):
        assert "test-bot" in bot.orchestrators
        assert len(bot.allowed_chat_ids) == 1

    def test_initialization_multiple_bots(self, multi_bot):
        assert len(multi_bot.orchestrators) == 3
        assert len(multi_bot.allowed_chat_ids) == 2

    def test_handlers_registered(self, bot):
        # The router should have handlers registered
        assert bot.router is not None
        assert bot.dp is not None

    def test_redis_initially_none(self, bot):
        assert bot.redis_client is None
        assert bot.event_listener_task is None


# ===========================================================================
# State Emoji Mapping
# ===========================================================================


class TestStateEmoji:
    def test_state_emoji_mapping(self, bot):
        # BotState values should map to emojis
        emojis = {
            BotState.RUNNING: bot._get_state_emoji(BotState.RUNNING),
            BotState.STOPPED: bot._get_state_emoji(BotState.STOPPED),
            BotState.PAUSED: bot._get_state_emoji(BotState.PAUSED),
        }
        # Each state should have an emoji (non-empty string)
        for _state, emoji in emojis.items():
            assert isinstance(emoji, str)
            assert len(emoji) > 0
