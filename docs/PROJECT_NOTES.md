# DCNBot Project Notes

## Overview

DCNBot is a Meshtastic-to-Telegram gateway that bridges LoRa mesh networks with Telegram chat groups. It enables two-way communication between off-grid Meshtastic nodes and internet-connected Telegram users.

**Key Capabilities:**
- Relay messages bidirectionally between Meshtastic mesh and Telegram
- Automatic node discovery and naming
- Welcome messages for new nodes
- Message chunking for long texts
- Moderation/blocklist support
- CLI for direct mesh interaction

## Project Structure

```
dcnbot/
├── __init__.py                     # Package init with future annotations
├── cli/
│   ├── __init__.py
│   ├── cli.py                      # Command-line interface (nodes, send, dm)
│   └── test_cli.py                 # CLI tests (11 tests)
├── client/
│   ├── __init__.py
│   └── mqtt/
│       ├── __init__.py
│       ├── mqtt_client.py          # MQTT client with Meshtastic protocol
│       └── test_mqtt_client.py     # MQTT client tests (24 tests)
├── config/
│   ├── __init__.py
│   ├── config.py                   # INI configuration loader
│   └── test_config.py              # Config tests (26 tests)
├── database/
│   ├── __init__.py
│   ├── database.py                 # SQLite operations for node tracking
│   └── test_database.py            # Database tests (19 tests)
└── gateway/
    ├── __init__.py
    ├── gateway.py                  # Main async entry point
    ├── telegram_bot.py             # Mock Telegram bot implementation
    └── test_telegram_bot.py        # Telegram bot tests (9 tests)
```

**Statistics:**
- 18 Python files
- ~1300 lines of code
- 89 tests (all passing)

## Module Descriptions

### `config/config.py`
Configuration loader using Python's `configparser`. Reads settings from INI files with properties for:
- Telegram API credentials
- MQTT broker connection details
- Meshtastic channel settings (gateway ID, channel name/key, root topic)
- Relay enable/disable flags
- Welcome message settings
- Moderation blocklist
- Database path

### `database/database.py`
Thread-safe SQLite database manager for node tracking. Features:
- Node UPSERT operations (insert or update)
- Welcome message tracking
- Node name lookups (by ID or name)
- Stores: node_id, long_name, short_name, last_heard, coordinates, welcome_sent

### `client/mqtt/mqtt_client.py`
Async MQTT client for Meshtastic communication. Handles:
- AES-CTR encryption/decryption using channel key
- Protobuf message parsing (ServiceEnvelope, MeshPacket, Data)
- Message deduplication cache
- Automatic message chunking for long texts (220 byte limit)
- Welcome DM sending to new nodes
- Topic building for pub/sub

### `gateway/gateway.py`
Main entry point that orchestrates all components:
- Initializes Config, Database, MQTTClient, TelegramBot
- Runs MQTT and Telegram bot concurrently via `asyncio.gather()`
- Handles graceful shutdown

### `gateway/telegram_bot.py`
**Currently a mock implementation.** Provides the interface expected by other components:
- `run()` - Async loop that processes message queue
- `stop()` - Graceful shutdown
- `send_message_to_telegram(message)` - Queues messages (logs instead of sending)

### `cli/cli.py`
Command-line interface for direct mesh interaction:
- `nodes` - List all known nodes from database
- `send <message>` - Broadcast to mesh
- `dm <node> <message>` - Direct message to specific node
- `generate-id` - Generate random Meshtastic node ID

## Current Implementation Status

### Completed
- [x] Configuration management (INI file parsing)
- [x] SQLite database for node persistence
- [x] MQTT client with full Meshtastic protocol support
- [x] AES-CTR encryption/decryption
- [x] Message chunking for long messages
- [x] Welcome DM functionality
- [x] Moderation blocklist
- [x] Command-line interface
- [x] Mock Telegram bot (interface only)
- [x] Comprehensive test suite (89 tests)
- [x] Type hints throughout (`from __future__ import annotations`)
- [x] Linting (pylint 10.00/10)
- [x] Type checking (mypy passing)

### TODO
- [ ] **Real Telegram bot implementation**
  - Replace mock with `python-telegram-bot` library
  - Implement `/send` command handler
  - Implement `/dm` command handler
  - Implement `/nodes` command handler
  - Forward incoming Telegram messages to mesh
- [ ] Add configuration for Telegram command permissions
- [ ] Add rate limiting for mesh transmissions
- [ ] Add logging configuration options
- [ ] Consider adding metrics/monitoring

## Development

### Commands
```bash
make lint      # Run pylint (target: 10.00/10)
make mypy      # Run mypy type checker
make test      # Run pytest (89 tests)
make all       # Run all checks
```

### Installation
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install package in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running
```bash
# Gateway service
python -m dcnbot.gateway.gateway

# CLI commands
python -m dcnbot.cli.cli nodes
python -m dcnbot.cli.cli send Hello mesh!
python -m dcnbot.cli.cli dm !12345678 Hello node!

# Or use the installed script
dcnbot-cli nodes
```

## Dependencies

### Runtime
| Package | Purpose |
|---------|---------|
| aiomqtt | Async MQTT client |
| cryptography | AES-CTR encryption for Meshtastic |
| meshtastic | Protobuf definitions |

### Development
| Package | Purpose |
|---------|---------|
| mypy | Static type checking |
| pylint | Code linting |
| pytest | Test framework |
| pytest-asyncio | Async test support |
| pytest-cov | Coverage reporting |

## Configuration

Example `config.ini`:
```ini
[telegram]
api_key = YOUR_BOT_TOKEN
chat_id = YOUR_CHAT_ID

[mqtt]
host = mqtt.example.com
port = 1883
user = username
password = password
client_id = dcnbot  # optional

[meshtastic]
gateway_id = !abcd1234
channel_name = LongFast
channel_key = AQ==  # base64 encoded
root_topic = msh/US

[relay]
meshtastic_to_telegram_enabled = true
telegram_to_meshtastic_enabled = true

[welcome_message]
enabled = true
message = Welcome to the mesh!

[database]
path = ./meshtastic.sqlite

[moderation]
blocklist = !deadbeef, !12345678  # optional, comma-separated
```

## Architecture Notes

### Message Flow: Mesh → Telegram
1. MQTT client receives encrypted protobuf from broker
2. Decrypt using AES-CTR with channel key
3. Parse protobuf (ServiceEnvelope → MeshPacket → Data)
4. Check blocklist, dedupe cache
5. Extract text, look up sender name from DB
6. Format message: `[NodeName] message text`
7. Queue to Telegram bot

### Message Flow: Telegram → Mesh
1. Telegram bot receives command (e.g., `/send Hello`)
2. Extract message text
3. Encode as protobuf Data payload
4. Encrypt with AES-CTR
5. Wrap in MeshPacket and ServiceEnvelope
6. Publish to MQTT broker

### Encryption
- Algorithm: AES-128-CTR
- Key: Base64-decoded channel key
- Nonce: `packet_id (8 bytes) + sender_id (8 bytes)`

## Test Coverage

| Module | Tests | Coverage Areas |
|--------|-------|----------------|
| config | 26 | Loading, defaults, blocklist parsing |
| database | 19 | CRUD, welcome tracking, lookups |
| mqtt_client | 24 | Hash functions, topics, init, send |
| telegram_bot | 9 | Init, queue, lifecycle |
| cli | 11 | Commands, error handling |

## Known Issues / Considerations

1. **Mock Telegram Bot**: The Telegram bot is a stub - it logs messages but doesn't actually send to Telegram. This is intentional for development/testing.

2. **Protobuf Introspection**: Pylint cannot introspect meshtastic protobuf classes, hence `no-member` is disabled.

3. **Thread Safety**: Database uses threading lock for concurrent access. MQTT client uses asyncio patterns.

4. **Message Size**: Meshtastic has ~220 byte payload limit. Long messages are automatically chunked with `(1/N)` prefixes.
