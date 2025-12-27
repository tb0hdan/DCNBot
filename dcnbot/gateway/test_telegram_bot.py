"""Tests for the TelegramBot class."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dcnbot.config.config import Config
from dcnbot.database.database import MeshtasticDB
from dcnbot.gateway.telegram_bot import TelegramBot


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
    return MagicMock()


@pytest.fixture
def telegram_bot(config: Config, mqtt_client: MagicMock, db: MeshtasticDB) -> TelegramBot:
    """Create a TelegramBot instance."""
    return TelegramBot(config=config, mqtt_client=mqtt_client, db=db)


class TestTelegramBot:
    """Tests for TelegramBot class."""

    def test_init(self, telegram_bot: TelegramBot) -> None:
        """Test TelegramBot initialization."""
        assert telegram_bot.config is not None
        assert telegram_bot.mqtt_client is not None
        assert telegram_bot.db is not None
        assert telegram_bot._running is False

    def test_send_message_to_telegram(self, telegram_bot: TelegramBot) -> None:
        """Test sending a message to Telegram queue."""
        telegram_bot.send_message_to_telegram("Test message")
        assert telegram_bot._message_queue.qsize() == 1

    def test_send_multiple_messages(self, telegram_bot: TelegramBot) -> None:
        """Test sending multiple messages."""
        telegram_bot.send_message_to_telegram("Message 1")
        telegram_bot.send_message_to_telegram("Message 2")
        telegram_bot.send_message_to_telegram("Message 3")
        assert telegram_bot._message_queue.qsize() == 3

    @pytest.mark.asyncio
    async def test_stop(self, telegram_bot: TelegramBot) -> None:
        """Test stopping the bot."""
        telegram_bot._running = True
        await telegram_bot.stop()
        assert telegram_bot._running is False

    @pytest.mark.asyncio
    async def test_run_processes_messages(self, telegram_bot: TelegramBot) -> None:
        """Test that run() processes messages from the queue."""
        telegram_bot.send_message_to_telegram("Test message")

        # Start the bot and let it process one message
        async def run_briefly() -> None:
            task = asyncio.create_task(telegram_bot.run())
            await asyncio.sleep(0.1)  # Let it process
            await telegram_bot.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_briefly()
        # Message should have been processed (queue empty)
        assert telegram_bot._message_queue.empty()

    @pytest.mark.asyncio
    async def test_run_handles_cancellation(self, telegram_bot: TelegramBot) -> None:
        """Test that run() handles cancellation gracefully."""
        task = asyncio.create_task(telegram_bot.run())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


class TestTelegramBotMessageQueue:
    """Tests for TelegramBot message queue behavior."""

    def test_queue_is_async(self, telegram_bot: TelegramBot) -> None:
        """Test that the message queue is an asyncio Queue."""
        assert isinstance(telegram_bot._message_queue, asyncio.Queue)

    def test_queue_starts_empty(self, telegram_bot: TelegramBot) -> None:
        """Test that the queue starts empty."""
        assert telegram_bot._message_queue.empty()

    def test_message_order_preserved(self, telegram_bot: TelegramBot) -> None:
        """Test that message order is preserved in queue."""
        messages = ["First", "Second", "Third"]
        for msg in messages:
            telegram_bot.send_message_to_telegram(msg)

        retrieved = []
        while not telegram_bot._message_queue.empty():
            retrieved.append(telegram_bot._message_queue.get_nowait())

        assert retrieved == messages
