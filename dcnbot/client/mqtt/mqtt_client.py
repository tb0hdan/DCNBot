"""MQTT client for communicating with the Meshtastic network."""

from __future__ import annotations

import asyncio
import base64
import collections
import logging
import math
import random
from typing import TYPE_CHECKING, Any

import aiomqtt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2

if TYPE_CHECKING:
    from dcnbot.config.config import Config
    from dcnbot.database.database import MeshtasticDB
    from dcnbot.gateway.telegram_bot import TelegramBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

MAX_PAYLOAD_BYTES = 220
DUPLICATE_CACHE_SIZE = 100


def xor_hash(data: bytes) -> int:
    """Compute XOR hash of bytes."""
    result = 0
    for char in data:
        result ^= char
    return result


def generate_channel_hash(name: str, key: str) -> int:
    """Generate a channel hash from name and key."""
    key_bytes = base64.b64decode(key.encode('utf-8'))
    h_name = xor_hash(bytes(name, 'utf-8'))
    h_key = xor_hash(key_bytes)
    return h_name ^ h_key


class MQTTClient:
    """MQTT client for Meshtastic communication."""

    def __init__(self, config: Config, db: MeshtasticDB) -> None:
        self.config = config
        self.db = db
        self.telegram_bot: TelegramBot | None = None
        self.welcome_dm_lock = asyncio.Lock()

        self.client: aiomqtt.Client | None = None
        self.message_cache: collections.OrderedDict[tuple[int, int], bool] = (
            collections.OrderedDict()
        )

        # Load all Meshtastic settings from config
        self.gateway_id_hex = self.config.meshtastic_gateway_id
        self.gateway_id_int = int(self.gateway_id_hex.replace('!', ''), 16)
        self.channel_name = self.config.meshtastic_channel_name
        self.channel_key = self.config.meshtastic_channel_key
        self.root_topic = self.config.meshtastic_root_topic

    def _build_topic(self, is_subscribe: bool = False) -> str:
        """Build the standard MQTT topic for subscribing or publishing."""
        parts = [self.root_topic.strip('/'), self.channel_name]
        if is_subscribe:
            parts.append('#')
        else:
            parts.append(self.gateway_id_hex)
        return '/'.join(parts)

    async def run(self) -> None:
        """The main async loop for the gateway service."""
        subscribe_topic = self._build_topic(is_subscribe=True)

        client_kwargs: dict[str, Any] = {
            "hostname": self.config.mqtt_host,
            "port": self.config.mqtt_port,
            "username": self.config.mqtt_user,
            "password": self.config.mqtt_password,
        }
        if self.config.mqtt_client_id:
            client_kwargs["identifier"] = self.config.mqtt_client_id

        while True:
            try:
                async with aiomqtt.Client(**client_kwargs) as client:
                    self.client = client
                    logging.info(
                        "Connecting to MQTT broker at %s...", self.config.mqtt_host
                    )
                    logging.info("Successfully connected.")
                    logging.info("Subscribing to topic: %s", subscribe_topic)
                    await self.client.subscribe(subscribe_topic)
                    async for message in self.client.messages:
                        asyncio.create_task(self.process_message(message))
            except aiomqtt.MqttError as error:
                logging.error("MQTT error: %s. Reconnecting in 5 seconds...", error)
                self.client = None
                await asyncio.sleep(5)

    async def _send_welcome_dm(self, node_id: int) -> None:
        """Send the welcome DM and update the database."""
        async with self.welcome_dm_lock:
            if self.db.has_been_welcomed(node_id):
                return
            logging.info("Sending welcome DM to new node !%08x", node_id)
            data_payload = mesh_pb2.Data(
                portnum=portnums_pb2.TEXT_MESSAGE_APP,
                payload=self.config.welcome_message_text.encode("utf-8"),
                bitfield=3
            )
            await self._send_packet(data_payload, destination_id=node_id)
            self.db.update_node(node_id=node_id, welcome_message_sent=1)

    async def process_message(self, message: aiomqtt.Message) -> None:
        """Process a single raw protobuf message from MQTT."""
        try:
            payload = message.payload
            if not isinstance(payload, (bytes, bytearray)):
                return
            service_envelope = mqtt_pb2.ServiceEnvelope()
            service_envelope.ParseFromString(bytes(payload))
            mesh_packet = service_envelope.packet
            sender_node_id: int = getattr(mesh_packet, 'from')

            if sender_node_id in self.config.moderation_blocklist:
                logging.warning(
                    "Ignoring message from blocked node !%08x", sender_node_id
                )
                return

            message_key = (sender_node_id, mesh_packet.id)
            if message_key in self.message_cache:
                logging.debug(
                    "Duplicate message ignored: from !%08x with ID %d",
                    sender_node_id, mesh_packet.id
                )
                return

            self.message_cache[message_key] = True
            if len(self.message_cache) > DUPLICATE_CACHE_SIZE:
                self.message_cache.popitem(last=False)

            if sender_node_id == self.gateway_id_int:
                return

            if (self.config.welcome_message_enabled
                    and not self.db.has_been_welcomed(sender_node_id)):
                await self._send_welcome_dm(sender_node_id)

            key_bytes = base64.b64decode(self.channel_key.encode('ascii'))
            nonce = (
                mesh_packet.id.to_bytes(8, "little")
                + sender_node_id.to_bytes(8, "little")
            )
            cipher = Cipher(
                algorithms.AES(key_bytes),
                modes.CTR(nonce),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            decrypted_payload = (
                decryptor.update(mesh_packet.encrypted) + decryptor.finalize()
            )
            data_payload = mesh_pb2.Data()
            data_payload.ParseFromString(decrypted_payload)

            if data_payload.portnum == portnums_pb2.TEXT_MESSAGE_APP:
                if not self.config.relay_mesh_to_telegram:
                    return
                text = data_payload.payload.decode('utf-8')
                node_name = self.db.get_node_name(sender_node_id)
                if node_name == str(sender_node_id):
                    node_name = f"!{sender_node_id:08x}"
                formatted_message = f"[{node_name}] {text}"
                logging.info("Forwarding to Telegram: %s", formatted_message)
                if self.telegram_bot:
                    self.telegram_bot.send_message_to_telegram(formatted_message)

            elif data_payload.portnum == portnums_pb2.NODEINFO_APP:
                user_info = mesh_pb2.User()
                user_info.ParseFromString(data_payload.payload)
                logging.info(
                    "Received NodeInfo from !%08x: name='%s'",
                    sender_node_id, user_info.long_name
                )
                self.db.update_node(
                    node_id=sender_node_id,
                    long_name=user_info.long_name,
                    short_name=user_info.short_name
                )
        except Exception:
            logging.debug("Could not process packet", exc_info=True)

    async def _send_packet(
        self,
        data_payload: mesh_pb2.Data,
        destination_id: int = 0xFFFFFFFF
    ) -> None:
        """Encrypt and publish any Data payload using the single client."""
        if not self.client:
            logging.error("MQTT client not connected. Cannot send packet.")
            return

        logging.info("Sending packet to !%08x", destination_id)
        key_bytes = base64.b64decode(self.channel_key.encode('ascii'))
        packet_id = random.randint(0, 0xFFFFFFFF)
        nonce = (
            packet_id.to_bytes(8, "little")
            + self.gateway_id_int.to_bytes(8, "little")
        )
        cipher = Cipher(
            algorithms.AES(key_bytes),
            modes.CTR(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_payload = (
            encryptor.update(data_payload.SerializeToString()) + encryptor.finalize()
        )

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
            logging.info("Publishing to %s", publish_topic)
            await self.client.publish(publish_topic, payload, qos=1)
        except aiomqtt.MqttError as error:
            logging.error("Could not publish MQTT message: %s", error)

    async def _send_text(
        self,
        text: str,
        destination_id: int = 0xFFFFFFFF
    ) -> None:
        """Handle message splitting and sending for the gateway service."""
        text_bytes = text.encode("utf-8")
        if len(text_bytes) <= MAX_PAYLOAD_BYTES:
            data_payload = mesh_pb2.Data(
                portnum=portnums_pb2.TEXT_MESSAGE_APP, payload=text_bytes,
                bitfield=3 if destination_id != 0xFFFFFFFF else 1
            )
            await self._send_packet(data_payload, destination_id)
            return

        logging.info("Splitting long message into chunks.")
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

    async def send_text_to_mesh(self, text: str) -> None:
        """Send a broadcast text message to the mesh."""
        if not self.config.relay_telegram_to_mesh:
            return
        await self._send_text(text)

    async def send_text_to_mesh_dm(self, text: str, destination_id: int) -> None:
        """Send a direct text message to a specific node."""
        if not self.config.relay_telegram_to_mesh:
            return
        await self._send_text(text, destination_id)

    async def send_cli_message(
        self,
        text: str,
        destination_id: int = 0xFFFFFFFF
    ) -> bool:
        """Connect, send a message, and disconnect (for CLI use)."""
        client_kwargs: dict[str, Any] = {
            "hostname": self.config.mqtt_host,
            "port": self.config.mqtt_port,
            "username": self.config.mqtt_user,
            "password": self.config.mqtt_password,
        }
        if self.config.mqtt_client_id:
            client_kwargs["identifier"] = self.config.mqtt_client_id

        try:
            async with aiomqtt.Client(**client_kwargs) as client:
                logging.info("CLI connecting to MQTT to send a message...")

                text_bytes = text.encode("utf-8")
                if len(text_bytes) > MAX_PAYLOAD_BYTES:
                    logging.warning(
                        "CLI message is too long and will be truncated by the node."
                    )

                data_payload = mesh_pb2.Data(
                    portnum=portnums_pb2.TEXT_MESSAGE_APP, payload=text_bytes,
                    bitfield=3 if destination_id != 0xFFFFFFFF else 1
                )

                logging.info("Sending packet to !%08x", destination_id)
                key_bytes = base64.b64decode(self.channel_key.encode('ascii'))
                packet_id = random.randint(0, 0xFFFFFFFF)
                nonce = (
                    packet_id.to_bytes(8, "little")
                    + self.gateway_id_int.to_bytes(8, "little")
                )
                cipher = Cipher(
                    algorithms.AES(key_bytes),
                    modes.CTR(nonce),
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                encrypted_payload = (
                    encryptor.update(data_payload.SerializeToString())
                    + encryptor.finalize()
                )
                mesh_packet = mesh_pb2.MeshPacket(
                    id=packet_id, to=destination_id, hop_limit=5,
                    encrypted=encrypted_payload
                )
                setattr(mesh_packet, "from", self.gateway_id_int)
                mesh_packet.channel = generate_channel_hash(
                    self.channel_name, self.channel_key
                )
                service_envelope = mqtt_pb2.ServiceEnvelope(
                    channel_id=self.channel_name, gateway_id=self.gateway_id_hex
                )
                service_envelope.packet.CopyFrom(mesh_packet)
                publish_topic = self._build_topic()
                payload = service_envelope.SerializeToString()

                logging.info("Publishing to %s", publish_topic)
                await client.publish(publish_topic, payload, qos=1)
            return True
        except aiomqtt.MqttError as exc:
            logging.error("CLI failed to send message: %s", exc)
            return False
