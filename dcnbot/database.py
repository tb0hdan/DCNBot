# mtg/database.py
import logging
import sqlite3
import time
import threading

class MeshtasticDB:
    """
    Handles all database operations for the gateway.
    This class is thread-safe.
    """
    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.connection = self._create_connection()
        self._create_table()

    def _create_connection(self):
        """Creates a database connection."""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            logging.info(f"Successfully connected to SQLite database at {self.db_path}")
            return conn
        except sqlite3.Error as e:
            logging.error(f"Error connecting to database: {e}", exc_info=True)
            raise

    def _create_table(self):
        """Creates the nodes table with all required columns if it doesn't exist."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                # --- NEW: Added welcome_message_sent column ---
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
            except sqlite3.Error as e:
                logging.error(f"Error creating table: {e}", exc_info=True)

    def update_node(self, node_id, long_name=None, short_name=None, latitude=None, longitude=None, welcome_message_sent=None):
        """Inserts or updates a node's information using an efficient UPSERT."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                # --- NEW: Added welcome_message_sent to the query ---
                cursor.execute("""
                    INSERT INTO nodes (node_id, long_name, short_name, last_heard, latitude, longitude, welcome_message_sent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        long_name = COALESCE(excluded.long_name, long_name),
                        short_name = COALESCE(excluded.short_name, short_name),
                        last_heard = excluded.last_heard,
                        latitude = COALESCE(excluded.latitude, latitude),
                        longitude = COALESCE(excluded.longitude, longitude),
                        welcome_message_sent = COALESCE(excluded.welcome_message_sent, welcome_message_sent)
                """, (node_id, long_name, short_name, int(time.time()), latitude, longitude, welcome_message_sent))
                self.connection.commit()
                logging.debug(f"Updated node {node_id} in the database.")
            except sqlite3.Error as e:
                logging.error(f"Error updating node {node_id}: {e}", exc_info=True)

    def has_been_welcomed(self, node_id):
        """Checks if a welcome message has been sent to a node."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT welcome_message_sent FROM nodes WHERE node_id = ?", (str(node_id),))
                result = cursor.fetchone()
                # Returns True if result exists and welcome_message_sent is 1, otherwise False
                return result and result[0] == 1
            except sqlite3.Error:
                return False # Assume not welcomed if there's an error

    def get_node_name(self, node_id):
        """Retrieves the best available name for a node from the database."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT long_name, short_name FROM nodes WHERE node_id = ?", (str(node_id),))
                result = cursor.fetchone()

                if result:
                    long_name, short_name = result
                    if long_name:
                        return long_name
                    if short_name:
                        return short_name
                
                return str(node_id)
            except sqlite3.Error as e:
                logging.error(f"Error getting node name for {node_id}: {e}", exc_info=True)
                return str(node_id)

    def close(self):
        """Closes the database connection."""
        if self.connection:
            self.connection.close()
            logging.info("Database connection closed.")
            
   # Add this function inside the MeshtasticDB class in mtg/database.py

    def get_node_id_by_name(self, name):
        """Finds a node's integer ID by its long or short name."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                # The node_id in the DB is stored as a string, so we query for that first.
                cursor.execute("SELECT node_id FROM nodes WHERE long_name = ? OR short_name = ?", (name, name))
                result = cursor.fetchone()
                if result:
                    # Convert the string ID from the DB to an integer before returning
                    return int(result[0])
                return None
            except sqlite3.Error as e:
                logging.error(f"Error getting node ID for name {name}: {e}", exc_info=True)
                return None
                
    # Add this function inside the MeshtasticDB class in mtg/database.py

    def get_all_nodes(self):
        """Retrieves all nodes from the database."""
        with self.lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT node_id, long_name, short_name, last_heard FROM nodes ORDER BY last_heard DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logging.error(f"Error getting all nodes: {e}", exc_info=True)
                return []            
