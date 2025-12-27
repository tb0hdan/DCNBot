"""Tests for the MeshtasticDB class."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from dcnbot.database.database import MeshtasticDB


@pytest.fixture
def db_path() -> Path:
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
        return Path(f.name)


@pytest.fixture
def db(db_path: Path) -> Generator[MeshtasticDB, None, None]:
    """Create a MeshtasticDB instance."""
    database = MeshtasticDB(db_path=str(db_path))
    yield database
    database.close()


class TestMeshtasticDB:
    """Tests for MeshtasticDB class."""

    def test_create_database(self, db: MeshtasticDB) -> None:
        """Test database creation."""
        assert db.connection is not None

    def test_update_node_new(self, db: MeshtasticDB) -> None:
        """Test inserting a new node."""
        db.update_node(
            node_id=0x12345678,
            long_name="Test Node",
            short_name="TST"
        )
        name = db.get_node_name(0x12345678)
        assert name == "Test Node"

    def test_update_node_existing(self, db: MeshtasticDB) -> None:
        """Test updating an existing node."""
        db.update_node(node_id=0x12345678, long_name="Original")
        db.update_node(node_id=0x12345678, long_name="Updated")
        name = db.get_node_name(0x12345678)
        assert name == "Updated"

    def test_update_node_partial(self, db: MeshtasticDB) -> None:
        """Test partial update preserves existing data."""
        db.update_node(
            node_id=0x12345678,
            long_name="Long Name",
            short_name="SN"
        )
        # Update only long_name, short_name should be preserved
        db.update_node(node_id=0x12345678, long_name="New Long Name")
        nodes = db.get_all_nodes()
        assert len(nodes) == 1
        assert nodes[0][1] == "New Long Name"
        assert nodes[0][2] == "SN"

    def test_get_node_name_long_name(self, db: MeshtasticDB) -> None:
        """Test get_node_name returns long_name first."""
        db.update_node(
            node_id=0x12345678,
            long_name="Long Name",
            short_name="SN"
        )
        assert db.get_node_name(0x12345678) == "Long Name"

    def test_get_node_name_short_name_fallback(self, db: MeshtasticDB) -> None:
        """Test get_node_name falls back to short_name."""
        db.update_node(node_id=0x12345678, short_name="SN")
        assert db.get_node_name(0x12345678) == "SN"

    def test_get_node_name_id_fallback(self, db: MeshtasticDB) -> None:
        """Test get_node_name falls back to node ID."""
        assert db.get_node_name(0x12345678) == "305419896"

    def test_get_node_id_by_name_long(self, db: MeshtasticDB) -> None:
        """Test finding node by long name."""
        db.update_node(node_id=0x12345678, long_name="Test Node")
        result = db.get_node_id_by_name("Test Node")
        assert result == 0x12345678

    def test_get_node_id_by_name_short(self, db: MeshtasticDB) -> None:
        """Test finding node by short name."""
        db.update_node(node_id=0x12345678, short_name="TST")
        result = db.get_node_id_by_name("TST")
        assert result == 0x12345678

    def test_get_node_id_by_name_not_found(self, db: MeshtasticDB) -> None:
        """Test finding non-existent node returns None."""
        result = db.get_node_id_by_name("NonExistent")
        assert result is None

    def test_get_all_nodes_empty(self, db: MeshtasticDB) -> None:
        """Test getting all nodes from empty database."""
        nodes = db.get_all_nodes()
        assert nodes == []

    def test_get_all_nodes(self, db: MeshtasticDB) -> None:
        """Test getting all nodes."""
        db.update_node(node_id=0x11111111, long_name="Node 1")
        db.update_node(node_id=0x22222222, long_name="Node 2")
        db.update_node(node_id=0x33333333, long_name="Node 3")
        nodes = db.get_all_nodes()
        assert len(nodes) == 3

    def test_has_been_welcomed_false(self, db: MeshtasticDB) -> None:
        """Test has_been_welcomed returns False for new node."""
        db.update_node(node_id=0x12345678, long_name="Test")
        assert db.has_been_welcomed(0x12345678) is False

    def test_has_been_welcomed_true(self, db: MeshtasticDB) -> None:
        """Test has_been_welcomed returns True after welcome sent."""
        db.update_node(node_id=0x12345678, welcome_message_sent=1)
        assert db.has_been_welcomed(0x12345678) is True

    def test_has_been_welcomed_unknown_node(self, db: MeshtasticDB) -> None:
        """Test has_been_welcomed returns False for unknown node."""
        assert db.has_been_welcomed(0x99999999) is False

    def test_update_welcome_message_sent(self, db: MeshtasticDB) -> None:
        """Test updating welcome_message_sent flag."""
        db.update_node(node_id=0x12345678, long_name="Test")
        assert db.has_been_welcomed(0x12345678) is False
        db.update_node(node_id=0x12345678, welcome_message_sent=1)
        assert db.has_been_welcomed(0x12345678) is True

    def test_node_with_coordinates(self, db: MeshtasticDB) -> None:
        """Test storing node with coordinates."""
        db.update_node(
            node_id=0x12345678,
            long_name="GPS Node",
            latitude=37.7749,
            longitude=-122.4194
        )
        nodes = db.get_all_nodes()
        assert len(nodes) == 1

    def test_close_database(self, db_path: Path) -> None:
        """Test closing database connection."""
        database = MeshtasticDB(db_path=str(db_path))
        database.close()
        # Connection should be closed, but object still exists
        assert database.connection is not None


class TestMeshtasticDBThreadSafety:
    """Tests for MeshtasticDB thread safety."""

    def test_lock_exists(self, db: MeshtasticDB) -> None:
        """Test that lock object exists."""
        assert db.lock is not None
