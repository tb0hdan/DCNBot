"""Tests for the MQTTClient class."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dcnbot.client.mqtt.mqtt_client import (
    MQTTClient,
    generate_channel_hash,
    xor_hash,
)
from dcnbot.config.config import Config
from dcnbot.database.database import MeshtasticDB


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
user = test_user
password = test_pass
client_id = test_client

[meshtastic]
gateway_id = !abcd1234
channel_name = LongFast
channel_key = AQ==
root_topic = msh/test

[relay]
meshtastic_to_telegram_enabled = true
telegram_to_meshtastic_enabled = true

[welcome_message]
enabled = false
message = Welcome!

[database]
path = ./test.sqlite

[moderation]
blocklist = !deadbeef
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
    mock_db = MagicMock(spec=MeshtasticDB)
    mock_db.has_been_welcomed.return_value = False
    mock_db.get_node_name.return_value = "TestNode"
    return mock_db


@pytest.fixture
def mqtt_client(config: Config, db: MeshtasticDB) -> MQTTClient:
    """Create an MQTTClient instance."""
    return MQTTClient(config=config, db=db)


class TestXorHash:
    """Tests for xor_hash function."""

    def test_empty_bytes(self) -> None:
        """Test XOR hash of empty bytes."""
        assert xor_hash(b"") == 0

    def test_single_byte(self) -> None:
        """Test XOR hash of single byte."""
        assert xor_hash(b"\x42") == 0x42

    def test_multiple_bytes(self) -> None:
        """Test XOR hash of multiple bytes."""
        # 0x01 ^ 0x02 ^ 0x03 = 0
        assert xor_hash(b"\x01\x02\x03") == 0

    def test_known_value(self) -> None:
        """Test XOR hash with known value."""
        # 'A' = 0x41, 'B' = 0x42 -> 0x41 ^ 0x42 = 0x03
        assert xor_hash(b"AB") == 0x03


class TestGenerateChannelHash:
    """Tests for generate_channel_hash function."""

    def test_generates_integer(self) -> None:
        """Test that channel hash is an integer."""
        result = generate_channel_hash("LongFast", "AQ==")
        assert isinstance(result, int)

    def test_deterministic(self) -> None:
        """Test that same inputs produce same output."""
        hash1 = generate_channel_hash("TestChannel", "AQ==")
        hash2 = generate_channel_hash("TestChannel", "AQ==")
        assert hash1 == hash2

    def test_different_names_different_hash(self) -> None:
        """Test that different names produce different hashes."""
        hash1 = generate_channel_hash("Channel1", "AQ==")
        hash2 = generate_channel_hash("Channel2", "AQ==")
        assert hash1 != hash2

    def test_different_keys_different_hash(self) -> None:
        """Test that different keys produce different hashes."""
        hash1 = generate_channel_hash("Test", "AQ==")
        hash2 = generate_channel_hash("Test", "Ag==")
        assert hash1 != hash2


class TestMQTTClientInit:
    """Tests for MQTTClient initialization."""

    def test_init_config(self, mqtt_client: MQTTClient, config: Config) -> None:
        """Test that config is stored."""
        assert mqtt_client.config is config

    def test_init_db(self, mqtt_client: MQTTClient, db: MeshtasticDB) -> None:
        """Test that database is stored."""
        assert mqtt_client.db is db

    def test_init_telegram_bot_none(self, mqtt_client: MQTTClient) -> None:
        """Test that telegram_bot starts as None."""
        assert mqtt_client.telegram_bot is None

    def test_init_gateway_id_hex(self, mqtt_client: MQTTClient) -> None:
        """Test gateway ID hex is loaded."""
        assert mqtt_client.gateway_id_hex == "!abcd1234"

    def test_init_gateway_id_int(self, mqtt_client: MQTTClient) -> None:
        """Test gateway ID is converted to int."""
        assert mqtt_client.gateway_id_int == 0xABCD1234

    def test_init_channel_name(self, mqtt_client: MQTTClient) -> None:
        """Test channel name is loaded."""
        assert mqtt_client.channel_name == "LongFast"

    def test_init_channel_key(self, mqtt_client: MQTTClient) -> None:
        """Test channel key is loaded."""
        assert mqtt_client.channel_key == "AQ=="

    def test_init_root_topic(self, mqtt_client: MQTTClient) -> None:
        """Test root topic is loaded."""
        assert mqtt_client.root_topic == "msh/test"

    def test_init_client_none(self, mqtt_client: MQTTClient) -> None:
        """Test MQTT client starts as None."""
        assert mqtt_client.client is None

    def test_init_message_cache_empty(self, mqtt_client: MQTTClient) -> None:
        """Test message cache starts empty."""
        assert len(mqtt_client.message_cache) == 0


class TestMQTTClientBuildTopic:
    """Tests for MQTTClient._build_topic method."""

    def test_build_subscribe_topic(self, mqtt_client: MQTTClient) -> None:
        """Test building subscribe topic."""
        topic = mqtt_client._build_topic(is_subscribe=True)
        assert topic == "msh/test/LongFast/#"

    def test_build_publish_topic(self, mqtt_client: MQTTClient) -> None:
        """Test building publish topic."""
        topic = mqtt_client._build_topic(is_subscribe=False)
        assert topic == "msh/test/LongFast/!abcd1234"

    def test_build_topic_default_publish(self, mqtt_client: MQTTClient) -> None:
        """Test default is publish topic."""
        topic = mqtt_client._build_topic()
        assert topic == "msh/test/LongFast/!abcd1234"


class TestMQTTClientSendText:
    """Tests for MQTTClient text sending methods."""

    @pytest.mark.asyncio
    async def test_send_text_to_mesh_disabled(
        self, config_file: Path, db: MeshtasticDB
    ) -> None:
        """Test send_text_to_mesh does nothing when relay disabled."""
        # Modify config to disable relay
        config_content = """\
[telegram]
api_key = test_key
chat_id = 123

[mqtt]
host = localhost
port = 1883

[meshtastic]
gateway_id = !abcd1234
channel_name = LongFast
channel_key = AQ==
root_topic = msh/test

[relay]
telegram_to_meshtastic_enabled = false

[database]
path = ./test.sqlite
"""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.ini', delete=False
        ) as f:
            f.write(config_content)
            config_path = f.name

        disabled_config = Config(config_path=config_path)
        client = MQTTClient(config=disabled_config, db=db)
        # This should return early without error
        await client.send_text_to_mesh("Test message")

    @pytest.mark.asyncio
    async def test_send_text_to_mesh_dm_disabled(
        self, config_file: Path, db: MeshtasticDB
    ) -> None:
        """Test send_text_to_mesh_dm does nothing when relay disabled."""
        config_content = """\
[telegram]
api_key = test_key
chat_id = 123

[mqtt]
host = localhost
port = 1883

[meshtastic]
gateway_id = !abcd1234
channel_name = LongFast
channel_key = AQ==
root_topic = msh/test

[relay]
telegram_to_meshtastic_enabled = false

[database]
path = ./test.sqlite
"""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.ini', delete=False
        ) as f:
            f.write(config_content)
            config_path = f.name

        disabled_config = Config(config_path=config_path)
        client = MQTTClient(config=disabled_config, db=db)
        # This should return early without error
        await client.send_text_to_mesh_dm("Test message", 0x12345678)


class TestMQTTClientSendPacket:
    """Tests for MQTTClient._send_packet method."""

    @pytest.mark.asyncio
    async def test_send_packet_no_client(self, mqtt_client: MQTTClient) -> None:
        """Test _send_packet does nothing when client is None."""
        mqtt_client.client = None
        # Create a mock Data payload
        mock_data = MagicMock()
        mock_data.SerializeToString.return_value = b"test"

        # Should return without error
        await mqtt_client._send_packet(mock_data)
