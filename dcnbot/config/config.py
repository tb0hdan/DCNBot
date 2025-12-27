# mtg/config.py
import configparser
import logging

class Config:
    def __init__(self, config_path='config.ini'):
        self.config_path = config_path
        self.parser = configparser.ConfigParser()
        self.read()

    def read(self):
        logging.info(f"Reading configuration from {self.config_path}")
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.parser.read_file(f)
        except FileNotFoundError:
            logging.error(f"Configuration file not found at {self.config_path}.")
            raise

    # --- Moderation Settings ---
    @property
    def moderation_blocklist(self):
        blocklist_str = self.parser.get('moderation', 'blocklist', fallback='')
        if not blocklist_str:
            return set()
        id_strings = [item.strip().lstrip('!') for item in blocklist_str.split(',')]
        blocklist_set = set()
        for hex_id in id_strings:
            if hex_id:
                try:
                    blocklist_set.add(int(hex_id, 16))
                except ValueError:
                    logging.warning(f"Invalid hex ID '{hex_id}' in blocklist, ignoring.")
        return blocklist_set

    # --- Meshtastic Settings ---
    @property
    def meshtastic_gateway_id(self):
        return self.parser.get('meshtastic', 'gateway_id')

    @property
    def meshtastic_channel_name(self):
        return self.parser.get('meshtastic', 'channel_name')

    @property
    def meshtastic_channel_key(self):
        return self.parser.get('meshtastic', 'channel_key')

    @property
    def meshtastic_root_topic(self):
        return self.parser.get('meshtastic', 'root_topic')

    # --- Welcome Message Settings ---
    @property
    def welcome_message_enabled(self):
        return self.parser.getboolean('welcome_message', 'enabled', fallback=False)

    @property
    def welcome_message_text(self):
        return self.parser.get('welcome_message', 'message', fallback="")

    # --- Relay Settings ---
    @property
    def relay_mesh_to_telegram(self):
        return self.parser.getboolean('relay', 'meshtastic_to_telegram_enabled', fallback=True)

    @property
    def relay_telegram_to_mesh(self):
        return self.parser.getboolean('relay', 'telegram_to_meshtastic_enabled', fallback=True)

    # --- Telegram Settings ---
    @property
    def telegram_api_key(self):
        return self.parser.get('telegram', 'api_key')

    @property
    def telegram_chat_id(self):
        return self.parser.get('telegram', 'chat_id')

    # --- MQTT Settings ---
    @property
    def mqtt_host(self):
        return self.parser.get('mqtt', 'host')

    @property
    def mqtt_port(self):
        return self.parser.getint('mqtt', 'port')

    @property
    def mqtt_user(self):
        return self.parser.get('mqtt', 'user', fallback=None)

    @property
    def mqtt_password(self):
        return self.parser.get('mqtt', 'password', fallback=None)
        
    @property
    def mqtt_client_id(self):
        client_id = self.parser.get('mqtt', 'client_id', fallback=None)
        return client_id if client_id else None

    # --- Database Settings ---
    @property
    def db_path(self):
        return self.parser.get('database', 'path')
