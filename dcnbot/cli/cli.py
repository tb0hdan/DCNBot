"""Command-line interface for the Meshtastic-Telegram Gateway."""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time

from dcnbot.client.mqtt.mqtt_client import MQTTClient
from dcnbot.config.config import Config
from dcnbot.database.database import MeshtasticDB


async def main() -> None:
    """The main entry point for the CLI."""
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(
        description="Command-line interface for the Meshtastic-Telegram Gateway."
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Sub-parser for the 'generate-id' command
    subparsers.add_parser('generate-id', help='Generate a new random hex ID for a node.')

    # Sub-parser for the 'nodes' command
    subparsers.add_parser('nodes', help='List all known nodes from the database.')

    # Sub-parser for the 'send' command
    send_parser = subparsers.add_parser('send', help='Send a broadcast message to the mesh.')
    send_parser.add_argument('message', nargs='+', help='The message to send.')

    # Sub-parser for the 'dm' command
    dm_parser = subparsers.add_parser('dm', help='Send a direct message to a specific node.')
    dm_parser.add_argument(
        'node', help='The name or hex ID (e.g., !a1b2c3d4) of the destination node.'
    )
    dm_parser.add_argument('message', nargs='+', help='The message to send.')

    args = parser.parse_args()

    # Handle the 'generate-id' command
    if args.command == 'generate-id':
        # A 32-bit integer, same as Meshtastic node IDs
        random_id = random.randint(0, 0xFFFFFFFF)
        hex_id = f"!{random_id:08x}"
        print("Generated new random Meshtastic node ID:")
        print(hex_id)
        return

    # Initialize components for other commands
    config = Config(config_path='config.ini')
    db = MeshtasticDB(db_path=config.db_path)

    try:
        if args.command == 'nodes':
            _handle_nodes_command(db)
        elif args.command in ['send', 'dm']:
            await _handle_message_command(args, config, db)
    finally:
        if db:
            db.close()


def _handle_nodes_command(db: MeshtasticDB) -> None:
    """Handle the 'nodes' command to list all known nodes."""
    nodes = db.get_all_nodes()
    if not nodes:
        print("No nodes found in the database.")
        return

    print(f"{'Node ID':<12} {'Long Name':<25} {'Short Name':<12} {'Last Heard'}")
    print(f"{'-'*12} {'-'*25} {'-'*12} {'-'*12}")
    for node in nodes:
        node_id, long_name, short_name, last_heard = node
        node_id_hex = f"!{int(node_id):08x}"
        last_heard_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(last_heard))
        print(
            f"{node_id_hex:<12} {str(long_name or ''):<25} "
            f"{str(short_name or ''):<12} {last_heard_str}"
        )


async def _handle_message_command(
    args: argparse.Namespace,
    config: Config,
    db: MeshtasticDB
) -> None:
    """Handle the 'send' and 'dm' commands."""
    mqtt = MQTTClient(config=config, db=db)
    message_text = " ".join(args.message)
    destination_id = 0xFFFFFFFF

    if args.command == 'dm':
        node_identifier = args.node
        if node_identifier.startswith('!'):
            try:
                destination_id = int(node_identifier[1:], 16)
            except ValueError:
                print(f"Error: Invalid hex node ID '{node_identifier}'.")
                return
        else:
            found_id = db.get_node_id_by_name(node_identifier)
            if found_id is None:
                print(f"Error: Node '{node_identifier}' not found in the database.")
                return
            destination_id = found_id

    success = await mqtt.send_cli_message(message_text, destination_id)
    if success:
        print("Message sent successfully.")
    else:
        print("Failed to send message. Check connection details and broker status.")


def run_cli() -> None:
    """Entry point for the CLI."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled.")


if __name__ == '__main__':
    run_cli()
