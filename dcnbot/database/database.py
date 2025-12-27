"""Database operations for the Meshtastic-Telegram Gateway."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from typing import Any


class MeshtasticDB:
    """
    Handles all database operations for the gateway.

    This class is thread-safe.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self.connection = self._create_connection()
        self._create_table()

    def _create_connection(self) -> sqlite3.Connection:
        """Create a database connection."""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            logging.info("Successfully connected to SQLite database at %s", self.db_path)
            return conn
        except sqlite3.Error:
            logging.exception("Error connecting to database")
            raise

    def _create_table(self) -> None:
        """Create the nodes table with all required columns if it doesn't exist."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS nodes (
                        node_id TEXT PRIMARY KEY,
                        long_name TEXT,
                        short_name TEXT,
                        last_heard INTEGER,
                        latitude REAL,
                        longitude REAL,
                        welcome_message_sent INTEGER DEFAULT 0
                    )
                """)
                self.connection.commit()
                logging.info("Database table 'nodes' is ready.")
            except sqlite3.Error:
                logging.exception("Error creating table")

    def update_node(
        self,
        node_id: int | str,
        long_name: str | None = None,
        short_name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        welcome_message_sent: int | None = None
    ) -> None:
        """Insert or update a node's information using an efficient UPSERT."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute("""
                    INSERT INTO nodes (
                        node_id, long_name, short_name, last_heard,
                        latitude, longitude, welcome_message_sent
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        long_name = COALESCE(excluded.long_name, long_name),
                        short_name = COALESCE(excluded.short_name, short_name),
                        last_heard = excluded.last_heard,
                        latitude = COALESCE(excluded.latitude, latitude),
                        longitude = COALESCE(excluded.longitude, longitude),
                        welcome_message_sent = COALESCE(
                            excluded.welcome_message_sent, welcome_message_sent
                        )
                """, (
                    node_id, long_name, short_name, int(time.time()),
                    latitude, longitude, welcome_message_sent
                ))
                self.connection.commit()
                logging.debug("Updated node %s in the database.", node_id)
            except sqlite3.Error:
                logging.exception("Error updating node %s", node_id)

    def has_been_welcomed(self, node_id: int | str) -> bool:
        """Check if a welcome message has been sent to a node."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute(
                    "SELECT welcome_message_sent FROM nodes WHERE node_id = ?",
                    (str(node_id),)
                )
                result = cursor.fetchone()
                # Returns True if result exists and welcome_message_sent is 1
                return bool(result and result[0] == 1)
            except sqlite3.Error:
                return False  # Assume not welcomed if there's an error

    def get_node_name(self, node_id: int | str) -> str:
        """Retrieve the best available name for a node from the database."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute(
                    "SELECT long_name, short_name FROM nodes WHERE node_id = ?",
                    (str(node_id),)
                )
                result = cursor.fetchone()

                if result:
                    long_name, short_name = result
                    if long_name:
                        return str(long_name)
                    if short_name:
                        return str(short_name)

                return str(node_id)
            except sqlite3.Error:
                logging.exception("Error getting node name for %s", node_id)
                return str(node_id)

    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            logging.info("Database connection closed.")

    def get_node_id_by_name(self, name: str) -> int | None:
        """Find a node's integer ID by its long or short name."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute(
                    "SELECT node_id FROM nodes WHERE long_name = ? OR short_name = ?",
                    (name, name)
                )
                result = cursor.fetchone()
                if result:
                    return int(result[0])
                return None
            except sqlite3.Error:
                logging.exception("Error getting node ID for name %s", name)
                return None

    def get_all_nodes(self) -> list[tuple[Any, ...]]:
        """Retrieve all nodes from the database."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute(
                    "SELECT node_id, long_name, short_name, last_heard "
                    "FROM nodes ORDER BY last_heard DESC"
                )
                return cursor.fetchall()
            except sqlite3.Error:
                logging.exception("Error getting all nodes")
                return []
