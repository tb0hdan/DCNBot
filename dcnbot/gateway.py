# mtg/gateway.py
import asyncio
import logging
from .config import Config
from .database import MeshtasticDB
from .mqtt_client import MQTTClient
from .telegram_bot import TelegramBot

async def main():
    """The main entry point for the gateway."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Logging initialized.")

    # Define components in the outer scope to access them in the finally block
    db = None
    bot = None
    
    try:
        # Initialize components
        config = Config(config_path='config.ini')
        logging.info("Configuration loaded successfully.")

        db = MeshtasticDB(db_path=config.db_path)
        mqtt = MQTTClient(config=config, db=db)
        bot = TelegramBot(config=config, mqtt_client=mqtt, db=db)

        # Link components
        mqtt.telegram_bot = bot

        # Start services
        logging.info("Gateway is fully running. Press Ctrl+C to exit.")
        
        # Run MQTT client and Telegram bot concurrently
        await asyncio.gather(
            mqtt.run(),
            bot.run()
        )

    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Gateway shutting down...")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        # --- CORRECTED SHUTDOWN LOGIC ---
        # Gracefully stop the Telegram bot first to clean up its tasks.
        if bot:
            await bot.stop()
        # Then, close the database connection.
        if db:
            db.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This catch is to prevent the default Python traceback from showing
        # when the user presses Ctrl+C to stop the cleanly shut down program.
        logging.info("Shutdown complete.")
