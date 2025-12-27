"""Tests for the Config class."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dcnbot.config.config import Config


@pytest.fixture
def sample_config_file() -> Path:
    """Create a temporary config file for testing."""
    config_content = """
[telegram]
api_key = test_api_key_123
chat_id = -123456789

[mqtt]
host = mqtt.example.com
port = 1883
user = mqtt_user
password = mqtt_pass
client_id = test_client

[meshtastic]
gateway_id = !abcd1234
channel_name = LongFast
channel_key = AQ==
root_topic = msh/test

[relay]
meshtastic_to_telegram_enabled = true
telegram_to_meshtastic_enabled = false

[welcome_message]
enabled = true
message = Welcome to the mesh!

[database]
path = ./test.sqlite

[moderation]
blocklist = !deadbeef, !12345678
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(config_content)
        return Path(f.name)


@pytest.fixture
def config(sample_config_file: Path) -> Config:
    """Create a Config instance from the sample config file."""
    return Config(config_path=str(sample_config_file))


class TestConfig:
    """Tests for Config class."""

    def test_telegram_api_key(self, config: Config) -> None:
        """Test reading Telegram API key."""
        assert config.telegram_api_key == "test_api_key_123"

    def test_telegram_chat_id(self, config: Config) -> None:
        """Test reading Telegram chat ID."""
        assert config.telegram_chat_id == "-123456789"

    def test_mqtt_host(self, config: Config) -> None:
        """Test reading MQTT host."""
        assert config.mqtt_host == "mqtt.example.com"

    def test_mqtt_port(self, config: Config) -> None:
        """Test reading MQTT port."""
        assert config.mqtt_port == 1883

    def test_mqtt_user(self, config: Config) -> None:
        """Test reading MQTT user."""
        assert config.mqtt_user == "mqtt_user"

    def test_mqtt_password(self, config: Config) -> None:
        """Test reading MQTT password."""
        assert config.mqtt_password == "mqtt_pass"

    def test_mqtt_client_id(self, config: Config) -> None:
        """Test reading MQTT client ID."""
        assert config.mqtt_client_id == "test_client"

    def test_meshtastic_gateway_id(self, config: Config) -> None:
        """Test reading Meshtastic gateway ID."""
        assert config.meshtastic_gateway_id == "!abcd1234"

    def test_meshtastic_channel_name(self, config: Config) -> None:
        """Test reading Meshtastic channel name."""
        assert config.meshtastic_channel_name == "LongFast"

    def test_meshtastic_channel_key(self, config: Config) -> None:
        """Test reading Meshtastic channel key."""
        assert config.meshtastic_channel_key == "AQ=="

    def test_meshtastic_root_topic(self, config: Config) -> None:
        """Test reading Meshtastic root topic."""
        assert config.meshtastic_root_topic == "msh/test"

    def test_relay_mesh_to_telegram(self, config: Config) -> None:
        """Test reading relay mesh to telegram setting."""
        assert config.relay_mesh_to_telegram is True

    def test_relay_telegram_to_mesh(self, config: Config) -> None:
        """Test reading relay telegram to mesh setting."""
        assert config.relay_telegram_to_mesh is False

    def test_welcome_message_enabled(self, config: Config) -> None:
        """Test reading welcome message enabled setting."""
        assert config.welcome_message_enabled is True

    def test_welcome_message_text(self, config: Config) -> None:
        """Test reading welcome message text."""
        assert config.welcome_message_text == "Welcome to the mesh!"

    def test_db_path(self, config: Config) -> None:
        """Test reading database path."""
        assert config.db_path == "./test.sqlite"

    def test_moderation_blocklist(self, config: Config) -> None:
        """Test reading moderation blocklist."""
        blocklist = config.moderation_blocklist
        assert isinstance(blocklist, set)
        assert len(blocklist) == 2
        assert 0xDEADBEEF in blocklist
        assert 0x12345678 in blocklist

    def test_config_file_not_found(self) -> None:
        """Test that FileNotFoundError is raised for missing config."""
        with pytest.raises(FileNotFoundError):
            Config(config_path="/nonexistent/config.ini")


class TestConfigDefaults:
    """Tests for Config default values."""

    @pytest.fixture
    def minimal_config_file(self) -> Path:
        """Create a minimal config file without optional sections."""
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
path = ./db.sqlite
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            return Path(f.name)

    @pytest.fixture
    def minimal_config(self, minimal_config_file: Path) -> Config:
        """Create a Config instance from minimal config."""
        return Config(config_path=str(minimal_config_file))

    def test_default_relay_mesh_to_telegram(self, minimal_config: Config) -> None:
        """Test default value for relay mesh to telegram."""
        assert minimal_config.relay_mesh_to_telegram is True

    def test_default_relay_telegram_to_mesh(self, minimal_config: Config) -> None:
        """Test default value for relay telegram to mesh."""
        assert minimal_config.relay_telegram_to_mesh is True

    def test_default_welcome_message_enabled(self, minimal_config: Config) -> None:
        """Test default value for welcome message enabled."""
        assert minimal_config.welcome_message_enabled is False

    def test_default_welcome_message_text(self, minimal_config: Config) -> None:
        """Test default value for welcome message text."""
        assert minimal_config.welcome_message_text == ""

    def test_default_mqtt_user(self, minimal_config: Config) -> None:
        """Test default value for MQTT user."""
        assert minimal_config.mqtt_user is None

    def test_default_mqtt_password(self, minimal_config: Config) -> None:
        """Test default value for MQTT password."""
        assert minimal_config.mqtt_password is None

    def test_default_mqtt_client_id(self, minimal_config: Config) -> None:
        """Test default value for MQTT client ID."""
        assert minimal_config.mqtt_client_id is None

    def test_default_moderation_blocklist(self, minimal_config: Config) -> None:
        """Test default value for moderation blocklist."""
        assert minimal_config.moderation_blocklist == set()
