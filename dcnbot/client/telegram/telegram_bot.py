"""Telegram bot for Meshtastic-Telegram gateway."""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


class TelegramBot:
    """
    Handles all Telegram bot functionality using asyncio.
    """
    def __init__(self, config, mqtt_client, db):
        self.config = config
        self.mqtt_client = mqtt_client
        self.db = db  # Store db instance for name lookups
        self.application = (
            Application.builder()
            .token(self.config.telegram_api_key)
            .build()
        )
        self._setup_handlers()

    async def run(self):
        """Starts the bot's polling loop."""
        logging.info("Starting Telegram bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self):
        """Stops the bot."""
        logging.info("Stopping Telegram bot...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

    def _setup_handlers(self):
        """Sets up command handlers instead of a general message handler."""
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("send", self._handle_send_command))
        self.application.add_handler(CommandHandler("dm", self._handle_dm_command))

    async def _start_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """Handles the /start command."""
        if update.message is None:
            return
        await update.message.reply_text(
            "Meshtastic-Telegram Gateway is running. Use /help for commands."
        )

    async def _help_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
        """Handles the /help command."""
        if update.message is None:
            return
        help_text = (
            "Available commands:\n"
            "/send <message> - Broadcasts a message to the mesh.\n"
            "/dm <name_or_id> <message> - Sends a direct message to a specific node."
        )
        await update.message.reply_text(help_text)

    async def _handle_send_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the /send command to broadcast a message."""
        if update.message is None or update.message.from_user is None:
            return

        if str(update.message.chat_id) != self.config.telegram_chat_id:
            logging.warning(
                "Ignoring command from unauthorized chat ID: %s", update.message.chat_id
            )
            return

        if not context.args:
            await update.message.reply_text("Usage: /send <your message>")
            return

        message_text = " ".join(context.args)
        sender_name = update.message.from_user.first_name
        message_to_mesh = f"<{sender_name}> {message_text}"

        logging.info("Forwarding broadcast from Telegram to mesh: '%s'", message_to_mesh)
        await self.mqtt_client.send_text_to_mesh(message_to_mesh)
        await update.message.reply_text("Broadcast message sent to the mesh.")

    async def _handle_dm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the /dm command to send a direct message."""
        if update.message is None or update.message.from_user is None:
            return

        if str(update.message.chat_id) != self.config.telegram_chat_id:
            logging.warning(
                "Ignoring command from unauthorized chat ID: %s", update.message.chat_id
            )
            return

        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Usage: /dm <node_name_or_id> <your message>")
            return

        node_identifier = context.args[0]
        message_text = " ".join(context.args[1:])
        destination_id = None

        if node_identifier.startswith('!'):
            try:
                destination_id = int(node_identifier[1:], 16)
            except ValueError:
                await update.message.reply_text(
                    f"Error: Invalid hex node ID '{node_identifier}'."
                )
                return
        else:
            destination_id = self.db.get_node_id_by_name(node_identifier)

        if destination_id is None:
            await update.message.reply_text(f"Error: Node '{node_identifier}' not found.")
            return

        sender_name = update.message.from_user.first_name
        message_to_mesh = f"<{sender_name}> {message_text}"

        logging.info(
            "Forwarding DM from Telegram to %s (!%08x): '%s'",
            node_identifier, destination_id, message_to_mesh
        )
        await self.mqtt_client.send_text_to_mesh_dm(message_to_mesh, destination_id)
        await update.message.reply_text(f"DM sent to {node_identifier}.")

    def send_message_to_telegram(self, message):
        """Sends a message to the configured Telegram chat."""
        asyncio.create_task(
            self.application.bot.send_message(
                chat_id=self.config.telegram_chat_id, text=message
            )
        )
