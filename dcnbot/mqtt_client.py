import asyncio
import logging
import aiomqtt
import time
import base64
import random
import math
import collections

from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAX_PAYLOAD_BYTES = 220
DUPLICATE_CACHE_SIZE = 100

def xor_hash(data: bytes) -> int:
    result = 0
    for char in data:
        result ^= char
    return result

def generate_channel_hash(name: str, key: str) -> int:
    key_bytes = base64.b64decode(key.encode('utf-8'))
    h_name = xor_hash(bytes(name, 'utf-8'))
    h_key = xor_hash(key_bytes)
    return h_name ^ h_key

class MQTTClient:
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.telegram_bot = None
        self.welcome_dm_lock = asyncio.Lock()
        
        self.client = None
        self.message_cache = collections.OrderedDict()
        
        # Load all Meshtastic settings from config
        self.gateway_id_hex = self.config.meshtastic_gateway_id
        self.gateway_id_int = int(self.gateway_id_hex.replace('!', ''), 16)
        self.channel_name = self.config.meshtastic_channel_name
        self.channel_key = self.config.meshtastic_channel_key
        self.root_topic = self.config.meshtastic_root_topic

    def _build_topic(self, is_subscribe=False):
        """Builds the standard MQTT topic for subscribing or publishing."""
        parts = [self.root_topic.strip('/'), self.channel_name]
        if is_subscribe:
            parts.append('#')
        else:
            parts.append(self.gateway_id_hex)
        return '/'.join(parts)

    async def run(self):
        """The main async loop for the gateway service."""
        subscribe_topic = self._build_topic(is_subscribe=True)
        
        client_kwargs = {
            "hostname": self.config.mqtt_host, "port": self.config.mqtt_port,
            "username": self.config.mqtt_user, "password": self.config.mqtt_password,
        }
        if self.config.mqtt_client_id:
            client_kwargs["identifier"] = self.config.mqtt_client_id

        while True:
            try:
                async with aiomqtt.Client(**client_kwargs) as client:
                    self.client = client
                    logging.info(f"Connecting to MQTT broker at {self.config.mqtt_host}...")
                    logging.info("Successfully connected.")
                    logging.info(f"Subscribing to topic: {subscribe_topic}")
                    await self.client.subscribe(subscribe_topic)
                    async for message in self.client.messages:
                        asyncio.create_task(self.process_message(message))
            except aiomqtt.MqttError as error:
                logging.error(f"MQTT error: {error}. Reconnecting in 5 seconds...")
                self.client = None
                await asyncio.sleep(5)

    async def _send_welcome_dm(self, node_id):
        """Sends the welcome DM and updates the database."""
        async with self.welcome_dm_lock:
            if self.db.has_been_welcomed(node_id):
                return
            logging.info(f"Sending welcome DM to new node !{node_id:08x}")
            data_payload = mesh_pb2.Data(
                portnum=portnums_pb2.TEXT_MESSAGE_APP,
                payload=self.config.welcome_message_text.encode("utf-8"),
                bitfield=3
            )
            await self._send_packet(data_payload, destination_id=node_id)
            self.db.update_node(node_id=node_id, welcome_message_sent=1)

    async def process_message(self, message):
        """Processes a single raw protobuf message from MQTT."""
        try:
            service_envelope = mqtt_pb2.ServiceEnvelope()
            service_envelope.ParseFromString(message.payload)
            mesh_packet = service_envelope.packet
            sender_node_id = getattr(mesh_packet, 'from')

            if sender_node_id in self.config.moderation_blocklist:
                logging.warning(f"Ignoring message from blocked node !{sender_node_id:08x}")
                return

            message_key = (sender_node_id, mesh_packet.id)
            if message_key in self.message_cache:
                logging.debug(f"Duplicate message ignored: from !{sender_node_id:08x} with ID {mesh_packet.id}")
                return
            
            self.message_cache[message_key] = True
            if len(self.message_cache) > DUPLICATE_CACHE_SIZE:
                self.message_cache.popitem(last=False)

            if sender_node_id == self.gateway_id_int:
                return

            if self.config.welcome_message_enabled and not self.db.has_been_welcomed(sender_node_id):
                await self._send_welcome_dm(sender_node_id)

            key_bytes = base64.b64decode(self.channel_key.encode('ascii'))
            nonce = mesh_packet.id.to_bytes(8, "little") + sender_node_id.to_bytes(8, "little")
            cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_payload = decryptor.update(mesh_packet.encrypted) + decryptor.finalize()
            data_payload = mesh_pb2.Data()
            data_payload.ParseFromString(decrypted_payload)

            if data_payload.portnum == portnums_pb2.TEXT_MESSAGE_APP:
                if not self.config.relay_mesh_to_telegram: return
                text = data_payload.payload.decode('utf-8')
                node_name = self.db.get_node_name(sender_node_id)
                if node_name == str(sender_node_id):
                    node_name = f"!{sender_node_id:08x}"
                formatted_message = f"[{node_name}] {text}"
                logging.info(f"Forwarding to Telegram: {formatted_message}")
                if self.telegram_bot:
                    self.telegram_bot.send_message_to_telegram(formatted_message)
            
            elif data_payload.portnum == portnums_pb2.NODEINFO_APP:
                user_info = mesh_pb2.User()
                user_info.ParseFromString(data_payload.payload)
                logging.info(f"Received NodeInfo from !{sender_node_id:08x}: name='{user_info.long_name}'")
                self.db.update_node(node_id=sender_node_id,
                                    long_name=user_info.long_name,
                                    short_name=user_info.short_name)
        except Exception as e:
            logging.debug(f"Could not process packet: {e}", exc_info=True)

    async def _send_packet(self, data_payload, destination_id=0xFFFFFFFF):
        """Internal function to encrypt and publish any Data payload using the single client."""
        if not self.client or not self.client._connected:
            logging.error("MQTT client not connected. Cannot send packet.")
            return
            
        logging.info(f"Sending packet to !{destination_id:08x}")
        key_bytes = base64.b64decode(self.channel_key.encode('ascii'))
        packet_id = random.randint(0, 0xFFFFFFFF)
        nonce = packet_id.to_bytes(8, "little") + self.gateway_id_int.to_bytes(8, "little")
        cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_payload = encryptor.update(data_payload.SerializeToString()) + encryptor.finalize()

        mesh_packet = mesh_pb2.MeshPacket(
            id=packet_id, to=destination_id, hop_limit=5,
            encrypted=encrypted_payload
        )
        setattr(mesh_packet, "from", self.gateway_id_int)
        mesh_packet.channel = generate_channel_hash(self.channel_name, self.channel_key)

        service_envelope = mqtt_pb2.ServiceEnvelope(
            channel_id=self.channel_name, gateway_id=self.gateway_id_hex
        )
        service_envelope.packet.CopyFrom(mesh_packet)
        publish_topic = self._build_topic()
        payload = service_envelope.SerializeToString()
        
        try:
            logging.info(f"Publishing to {publish_topic}")
            await self.client.publish(publish_topic, payload, qos=1)
        except aiomqtt.MqttError as error:
            logging.error(f"Could not publish MQTT message: {error}")

    async def _send_text(self, text, destination_id=0xFFFFFFFF):
        """Internal function to handle message splitting and sending for the gateway service."""
        text_bytes = text.encode("utf-8")
        if len(text_bytes) <= MAX_PAYLOAD_BYTES:
            data_payload = mesh_pb2.Data(
                portnum=portnums_pb2.TEXT_MESSAGE_APP, payload=text_bytes,
                bitfield=3 if destination_id != 0xFFFFFFFF else 1
            )
            await self._send_packet(data_payload, destination_id)
            return

        logging.info(f"Splitting long message into chunks.")
        prefix_placeholder = "(10/10) "
        available_space = MAX_PAYLOAD_BYTES - len(prefix_placeholder)
        num_chunks = math.ceil(len(text_bytes) / available_space)
        for i in range(num_chunks):
            part_prefix = f"({i+1}/{num_chunks}) "
            space = MAX_PAYLOAD_BYTES - len(part_prefix)
            start = i * space
            end = start + space
            chunk_with_prefix = part_prefix.encode("utf-8") + text_bytes[start:end]
            data_payload = mesh_pb2.Data(
                portnum=portnums_pb2.TEXT_MESSAGE_APP, payload=chunk_with_prefix,
                bitfield=3 if destination_id != 0xFFFFFFFF else 1
            )
            await self._send_packet(data_payload, destination_id)
            if i < num_chunks - 1:
                await asyncio.sleep(1)

    async def send_text_to_mesh(self, text):
        if not self.config.relay_telegram_to_mesh: return
        await self._send_text(text)

    async def send_text_to_mesh_dm(self, text, destination_id):
        if not self.config.relay_telegram_to_mesh: return
        await self._send_text(text, destination_id)

    async def send_cli_message(self, text, destination_id=0xFFFFFFFF):
        """A self-contained function for the CLI to connect, send a message, and disconnect."""
        client_kwargs = {
            "hostname": self.config.mqtt_host, "port": self.config.mqtt_port,
            "username": self.config.mqtt_user, "password": self.config.mqtt_password,
        }
        if self.config.mqtt_client_id:
            client_kwargs["identifier"] = self.config.mqtt_client_id
            
        try:
            async with aiomqtt.Client(**client_kwargs) as client:
                logging.info("CLI connecting to MQTT to send a message...")
                
                text_bytes = text.encode("utf-8")
                # Note: CLI message splitting is not implemented for brevity, but could be.
                if len(text_bytes) > MAX_PAYLOAD_BYTES:
                    logging.warning("CLI message is too long and will be truncated by the node.")

                data_payload = mesh_pb2.Data(
                    portnum=portnums_pb2.TEXT_MESSAGE_APP, payload=text_bytes,
                    bitfield=3 if destination_id != 0xFFFFFFFF else 1
                )

                logging.info(f"Sending packet to !{destination_id:08x}")
                key_bytes = base64.b64decode(self.channel_key.encode('ascii'))
                packet_id = random.randint(0, 0xFFFFFFFF)
                nonce = packet_id.to_bytes(8, "little") + self.gateway_id_int.to_bytes(8, "little")
                cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
                encryptor = cipher.encryptor()
                encrypted_payload = encryptor.update(data_payload.SerializeToString()) + encryptor.finalize()
                mesh_packet = mesh_pb2.MeshPacket(id=packet_id, to=destination_id, hop_limit=5, encrypted=encrypted_payload)
                setattr(mesh_packet, "from", self.gateway_id_int)
                mesh_packet.channel = generate_channel_hash(self.channel_name, self.channel_key)
                service_envelope = mqtt_pb2.ServiceEnvelope(channel_id=self.channel_name, gateway_id=self.gateway_id_hex)
                service_envelope.packet.CopyFrom(mesh_packet)
                publish_topic = self._build_topic()
                payload = service_envelope.SerializeToString()
                
                logging.info(f"Publishing to {publish_topic}")
                await client.publish(publish_topic, payload, qos=1)
            return True
        except aiomqtt.MqttError as e:
            logging.error(f"CLI failed to send message: {e}")
            return False
