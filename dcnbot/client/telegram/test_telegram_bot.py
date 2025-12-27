"""Tests for the TelegramBot class."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dcnbot.config.config import Config
from dcnbot.database.database import MeshtasticDB
from dcnbot.client.telegram.telegram_bot import TelegramBot


@pytest.fixture
def config_file() -> Path:
    """Create a temporary config file."""
    config_content = """
[telegram]
api_key = test_key
chat_id = 123

[mqtt]
host = localhost
port = 1883

[meshtastic]
gateway_id = !12345678
channel_name = test
channel_key = AQ==
root_topic = msh

[database]
path = ./test.sqlite
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(config_content)
        return Path(f.name)


@pytest.fixture
def config(config_file: Path) -> Config:
    """Create a Config instance."""
    return Config(config_path=str(config_file))


@pytest.fixture
def db() -> MeshtasticDB:
    """Create a mock MeshtasticDB instance."""
    return MagicMock(spec=MeshtasticDB)


@pytest.fixture
def mqtt_client() -> MagicMock:
    """Create a mock MQTTClient instance."""
    mock = MagicMock()
    mock.send_text_to_mesh = AsyncMock()
    mock.send_text_to_mesh_dm = AsyncMock()
    return mock


@pytest.fixture
def telegram_bot(config: Config, mqtt_client: MagicMock, db: MeshtasticDB) -> TelegramBot:
    """Create a TelegramBot instance."""
    with patch('dcnbot.client.telegram.telegram_bot.Application'):
        return TelegramBot(config=config, mqtt_client=mqtt_client, db=db)


class TestTelegramBot:
    """Tests for TelegramBot class."""

    def test_init(self, telegram_bot: TelegramBot) -> None:
        """Test TelegramBot initialization."""
        assert telegram_bot.config is not None
        assert telegram_bot.mqtt_client is not None
        assert telegram_bot.db is not None
        assert telegram_bot.application is not None

    def test_send_message_to_telegram(self, telegram_bot: TelegramBot) -> None:
        """Test sending a message to Telegram."""
        telegram_bot.application.bot.send_message = AsyncMock()
        with patch('asyncio.create_task') as mock_create_task:
            telegram_bot.send_message_to_telegram("Test message")
            mock_create_task.assert_called_once()

    def test_send_multiple_messages(self, telegram_bot: TelegramBot) -> None:
        """Test sending multiple messages."""
        telegram_bot.application.bot.send_message = AsyncMock()
        with patch('asyncio.create_task') as mock_create_task:
            telegram_bot.send_message_to_telegram("Message 1")
            telegram_bot.send_message_to_telegram("Message 2")
            telegram_bot.send_message_to_telegram("Message 3")
            assert mock_create_task.call_count == 3

    @pytest.mark.asyncio
    async def test_stop(self, telegram_bot: TelegramBot) -> None:
        """Test stopping the bot."""
        telegram_bot.application.updater = MagicMock()
        telegram_bot.application.updater.stop = AsyncMock()
        telegram_bot.application.stop = AsyncMock()
        telegram_bot.application.shutdown = AsyncMock()

        await telegram_bot.stop()

        telegram_bot.application.updater.stop.assert_called_once()
        telegram_bot.application.stop.assert_called_once()
        telegram_bot.application.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_starts_application(self, telegram_bot: TelegramBot) -> None:
        """Test that run() starts the application."""
        telegram_bot.application.initialize = AsyncMock()
        telegram_bot.application.start = AsyncMock()
        telegram_bot.application.updater = MagicMock()
        telegram_bot.application.updater.start_polling = AsyncMock()

        await telegram_bot.run()

        telegram_bot.application.initialize.assert_called_once()
        telegram_bot.application.start.assert_called_once()
        telegram_bot.application.updater.start_polling.assert_called_once()


class TestTelegramBotCommands:
    """Tests for TelegramBot command handlers."""

    @pytest.mark.asyncio
    async def test_start_command(self, telegram_bot: TelegramBot) -> None:
        """Test the /start command handler."""
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await telegram_bot._start_command(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "running" in call_args.lower()

    @pytest.mark.asyncio
    async def test_help_command(self, telegram_bot: TelegramBot) -> None:
        """Test the /help command handler."""
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await telegram_bot._help_command(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "/send" in call_args
        assert "/dm" in call_args

    @pytest.mark.asyncio
    async def test_send_command_unauthorized_chat(
        self, telegram_bot: TelegramBot, mqtt_client: MagicMock
    ) -> None:
        """Test /send command from unauthorized chat is ignored."""
        update = MagicMock()
        update.message.chat_id = 999  # Different from config chat_id (123)
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["test", "message"]

        await telegram_bot._handle_send_command(update, context)

        mqtt_client.send_text_to_mesh.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_command_no_args(self, telegram_bot: TelegramBot) -> None:
        """Test /send command with no arguments."""
        update = MagicMock()
        update.message.chat_id = 123  # Same as config
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = []

        await telegram_bot._handle_send_command(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_send_command_success(
        self, telegram_bot: TelegramBot, mqtt_client: MagicMock
    ) -> None:
        """Test successful /send command."""
        update = MagicMock()
        update.message.chat_id = 123
        update.message.from_user.first_name = "TestUser"
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["Hello", "mesh!"]

        await telegram_bot._handle_send_command(update, context)

        mqtt_client.send_text_to_mesh.assert_called_once()
        call_args = mqtt_client.send_text_to_mesh.call_args[0][0]
        assert "<TestUser>" in call_args
        assert "Hello mesh!" in call_args

    @pytest.mark.asyncio
    async def test_dm_command_no_args(self, telegram_bot: TelegramBot) -> None:
        """Test /dm command with insufficient arguments."""
        update = MagicMock()
        update.message.chat_id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["node_only"]  # Missing message

        await telegram_bot._handle_dm_command(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_dm_command_with_hex_id(
        self, telegram_bot: TelegramBot, mqtt_client: MagicMock
    ) -> None:
        """Test /dm command with hex node ID."""
        update = MagicMock()
        update.message.chat_id = 123
        update.message.from_user.first_name = "TestUser"
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["!abcd1234", "Hello", "node!"]

        await telegram_bot._handle_dm_command(update, context)

        mqtt_client.send_text_to_mesh_dm.assert_called_once()
        call_args = mqtt_client.send_text_to_mesh_dm.call_args[0]
        assert "<TestUser>" in call_args[0]
        assert "Hello node!" in call_args[0]
        assert call_args[1] == 0xabcd1234

    @pytest.mark.asyncio
    async def test_dm_command_node_not_found(
        self, telegram_bot: TelegramBot, db: MagicMock, mqtt_client: MagicMock
    ) -> None:
        """Test /dm command when node name is not found."""
        update = MagicMock()
        update.message.chat_id = 123
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["unknown_node", "Hello"]
        db.get_node_id_by_name.return_value = None

        await telegram_bot._handle_dm_command(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "not found" in call_args
        mqtt_client.send_text_to_mesh_dm.assert_not_called()
