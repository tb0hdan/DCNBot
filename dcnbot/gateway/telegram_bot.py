"""Mock Telegram Bot implementation for testing and development."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dcnbot.config.config import Config
    from dcnbot.client.mqtt.mqtt_client import MQTTClient
    from dcnbot.database.database import MeshtasticDB


class TelegramBot:
    """
    Mock implementation of the Telegram bot.

    This stub provides the interface expected by the gateway and MQTT client
    without requiring an actual Telegram bot token or connection.
    """

    def __init__(
        self,
        config: Config,
        mqtt_client: MQTTClient,
        db: MeshtasticDB,
    ) -> None:
        self.config = config
        self.mqtt_client = mqtt_client
        self.db = db
        self._running = False
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()
        logging.info("TelegramBot (mock) initialized.")

    async def run(self) -> None:
        """
        Main async loop for the Telegram bot.

        In a real implementation, this would poll for updates or use webhooks.
        This mock simply processes the message queue and logs messages.
        """
        self._running = True
        logging.info("TelegramBot (mock) started.")

        try:
            while self._running:
                try:
                    # Wait for messages with a timeout to allow checking _running
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=1.0
                    )
                    logging.info("[MOCK TELEGRAM] Would send: %s", message)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logging.info("TelegramBot (mock) run loop cancelled.")
            raise

    async def stop(self) -> None:
        """Stop the Telegram bot gracefully."""
        logging.info("TelegramBot (mock) stopping...")
        self._running = False

    def send_message_to_telegram(self, message: str) -> None:
        """
        Queue a message to be sent to Telegram.

        This is called synchronously from the MQTT client, so we use
        a queue to pass messages to the async run loop.

        Args:
            message: The formatted message to send to Telegram.
        """
        try:
            self._message_queue.put_nowait(message)
            logging.debug("Message queued for Telegram: %s", message)
        except asyncio.QueueFull:
            logging.warning("Telegram message queue full, dropping message.")
