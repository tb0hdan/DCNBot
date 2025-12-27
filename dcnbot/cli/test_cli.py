"""Tests for the CLI module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dcnbot.cli.cli import _handle_nodes_command, _handle_message_command
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

[meshtastic]
gateway_id = !abcd1234
channel_name = LongFast
channel_key = AQ==
root_topic = msh/test

[relay]
telegram_to_meshtastic_enabled = true

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
def mock_db() -> MagicMock:
    """Create a mock database."""
    db = MagicMock(spec=MeshtasticDB)
    db.get_all_nodes.return_value = []
    db.get_node_id_by_name.return_value = None
    return db


class TestHandleNodesCommand:
    """Tests for _handle_nodes_command function."""

    def test_empty_database(self, mock_db: MagicMock, capsys: pytest.CaptureFixture) -> None:
        """Test handling empty database."""
        mock_db.get_all_nodes.return_value = []
        _handle_nodes_command(mock_db)
        captured = capsys.readouterr()
        assert "No nodes found" in captured.out

    def test_with_nodes(self, mock_db: MagicMock, capsys: pytest.CaptureFixture) -> None:
        """Test handling database with nodes."""
        mock_db.get_all_nodes.return_value = [
            ("305419896", "Test Node", "TST", 1703721600),
        ]
        _handle_nodes_command(mock_db)
        captured = capsys.readouterr()
        assert "Node ID" in captured.out
        assert "Test Node" in captured.out

    def test_multiple_nodes(self, mock_db: MagicMock, capsys: pytest.CaptureFixture) -> None:
        """Test handling multiple nodes."""
        mock_db.get_all_nodes.return_value = [
            ("305419896", "Node 1", "N1", 1703721600),
            ("287454020", "Node 2", "N2", 1703721500),
        ]
        _handle_nodes_command(mock_db)
        captured = capsys.readouterr()
        assert "Node 1" in captured.out
        assert "Node 2" in captured.out

    def test_node_with_none_names(
        self, mock_db: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test handling node with None names."""
        mock_db.get_all_nodes.return_value = [
            ("305419896", None, None, 1703721600),
        ]
        _handle_nodes_command(mock_db)
        captured = capsys.readouterr()
        # Should not crash, should show empty strings
        assert "!12345678" in captured.out


class TestHandleMessageCommand:
    """Tests for _handle_message_command function."""

    @pytest.mark.asyncio
    async def test_send_broadcast(self, config: Config, mock_db: MagicMock) -> None:
        """Test sending a broadcast message."""
        args = MagicMock()
        args.command = "send"
        args.message = ["Hello", "World"]

        with patch("dcnbot.cli.cli.MQTTClient") as MockMQTTClient:
            mock_client = MagicMock()
            mock_client.send_cli_message = AsyncMock(return_value=True)
            MockMQTTClient.return_value = mock_client

            await _handle_message_command(args, config, mock_db)

            mock_client.send_cli_message.assert_called_once_with(
                "Hello World", 0xFFFFFFFF
            )

    @pytest.mark.asyncio
    async def test_send_dm_by_hex_id(self, config: Config, mock_db: MagicMock) -> None:
        """Test sending a DM by hex ID."""
        args = MagicMock()
        args.command = "dm"
        args.node = "!12345678"
        args.message = ["Test", "DM"]

        with patch("dcnbot.cli.cli.MQTTClient") as MockMQTTClient:
            mock_client = MagicMock()
            mock_client.send_cli_message = AsyncMock(return_value=True)
            MockMQTTClient.return_value = mock_client

            await _handle_message_command(args, config, mock_db)

            mock_client.send_cli_message.assert_called_once_with(
                "Test DM", 0x12345678
            )

    @pytest.mark.asyncio
    async def test_send_dm_by_name(self, config: Config, mock_db: MagicMock) -> None:
        """Test sending a DM by node name."""
        args = MagicMock()
        args.command = "dm"
        args.node = "TestNode"
        args.message = ["Hello"]

        mock_db.get_node_id_by_name.return_value = 0x12345678

        with patch("dcnbot.cli.cli.MQTTClient") as MockMQTTClient:
            mock_client = MagicMock()
            mock_client.send_cli_message = AsyncMock(return_value=True)
            MockMQTTClient.return_value = mock_client

            await _handle_message_command(args, config, mock_db)

            mock_db.get_node_id_by_name.assert_called_once_with("TestNode")
            mock_client.send_cli_message.assert_called_once_with("Hello", 0x12345678)

    @pytest.mark.asyncio
    async def test_send_dm_node_not_found(
        self, config: Config, mock_db: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test sending a DM to non-existent node."""
        args = MagicMock()
        args.command = "dm"
        args.node = "NonExistent"
        args.message = ["Hello"]

        mock_db.get_node_id_by_name.return_value = None

        await _handle_message_command(args, config, mock_db)

        captured = capsys.readouterr()
        assert "not found" in captured.out

    @pytest.mark.asyncio
    async def test_send_dm_invalid_hex(
        self, config: Config, mock_db: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test sending a DM with invalid hex ID."""
        args = MagicMock()
        args.command = "dm"
        args.node = "!invalidhex"
        args.message = ["Hello"]

        await _handle_message_command(args, config, mock_db)

        captured = capsys.readouterr()
        assert "Invalid hex node ID" in captured.out

    @pytest.mark.asyncio
    async def test_send_failure(
        self, config: Config, mock_db: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test handling send failure."""
        args = MagicMock()
        args.command = "send"
        args.message = ["Test"]

        with patch("dcnbot.cli.cli.MQTTClient") as MockMQTTClient:
            mock_client = MagicMock()
            mock_client.send_cli_message = AsyncMock(return_value=False)
            MockMQTTClient.return_value = mock_client

            await _handle_message_command(args, config, mock_db)

            captured = capsys.readouterr()
            assert "Failed to send" in captured.out

    @pytest.mark.asyncio
    async def test_send_success(
        self, config: Config, mock_db: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Test handling successful send."""
        args = MagicMock()
        args.command = "send"
        args.message = ["Test"]

        with patch("dcnbot.cli.cli.MQTTClient") as MockMQTTClient:
            mock_client = MagicMock()
            mock_client.send_cli_message = AsyncMock(return_value=True)
            MockMQTTClient.return_value = mock_client

            await _handle_message_command(args, config, mock_db)

            captured = capsys.readouterr()
            assert "successfully" in captured.out
