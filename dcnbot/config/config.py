"""Configuration management for the Meshtastic-Telegram Gateway."""

from __future__ import annotations

import configparser
import logging


class Config:
    """Configuration loader and accessor for gateway settings."""

    def __init__(self, config_path: str = 'configs/config.ini') -> None:
        self.config_path = config_path
        self.parser = configparser.ConfigParser()
        self.read()

    def read(self) -> None:
        """Read and parse the configuration file."""
        logging.info("Reading configuration from %s", self.config_path)
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.parser.read_file(f)
        except FileNotFoundError:
            logging.error("Configuration file not found at %s.", self.config_path)
            raise

    @property
    def moderation_blocklist(self) -> set[int]:
        """Get the set of blocked node IDs."""
        blocklist_str = self.parser.get('moderation', 'blocklist', fallback='')
        if not blocklist_str:
            return set()
        id_strings = [item.strip().lstrip('!') for item in blocklist_str.split(',')]
        blocklist_set: set[int] = set()
        for hex_id in id_strings:
            if hex_id:
                try:
                    blocklist_set.add(int(hex_id, 16))
                except ValueError:
                    logging.warning("Invalid hex ID '%s' in blocklist, ignoring.", hex_id)
        return blocklist_set

    @property
    def meshtastic_gateway_id(self) -> str:
        """Get the gateway node ID."""
        return self.parser.get('meshtastic', 'gateway_id')

    @property
    def meshtastic_channel_name(self) -> str:
        """Get the Meshtastic channel name."""
        return self.parser.get('meshtastic', 'channel_name')

    @property
    def meshtastic_channel_key(self) -> str:
        """Get the Meshtastic channel encryption key."""
        return self.parser.get('meshtastic', 'channel_key')

    @property
    def meshtastic_root_topic(self) -> str:
        """Get the MQTT root topic for Meshtastic."""
        return self.parser.get('meshtastic', 'root_topic')

    @property
    def welcome_message_enabled(self) -> bool:
        """Check if welcome messages are enabled."""
        return self.parser.getboolean('welcome_message', 'enabled', fallback=False)

    @property
    def welcome_message_text(self) -> str:
        """Get the welcome message text."""
        return self.parser.get('welcome_message', 'message', fallback="")

    @property
    def relay_mesh_to_telegram(self) -> bool:
        """Check if relay from mesh to Telegram is enabled."""
        return self.parser.getboolean('relay', 'meshtastic_to_telegram_enabled', fallback=True)

    @property
    def relay_telegram_to_mesh(self) -> bool:
        """Check if relay from Telegram to mesh is enabled."""
        return self.parser.getboolean('relay', 'telegram_to_meshtastic_enabled', fallback=True)

    @property
    def telegram_api_key(self) -> str:
        """Get the Telegram bot API key."""
        return self.parser.get('telegram', 'api_key')

    @property
    def telegram_chat_id(self) -> str:
        """Get the Telegram chat ID."""
        return self.parser.get('telegram', 'chat_id')

    @property
    def mqtt_host(self) -> str:
        """Get the MQTT broker hostname."""
        return self.parser.get('mqtt', 'host')

    @property
    def mqtt_port(self) -> int:
        """Get the MQTT broker port."""
        return self.parser.getint('mqtt', 'port')

    @property
    def mqtt_user(self) -> str | None:
        """Get the MQTT username."""
        return self.parser.get('mqtt', 'user', fallback=None)

    @property
    def mqtt_password(self) -> str | None:
        """Get the MQTT password."""
        return self.parser.get('mqtt', 'password', fallback=None)

    @property
    def mqtt_client_id(self) -> str | None:
        """Get the MQTT client ID."""
        client_id = self.parser.get('mqtt', 'client_id', fallback=None)
        return client_id if client_id else None

    @property
    def db_path(self) -> str:
        """Get the database file path."""
        return self.parser.get('database', 'path')
