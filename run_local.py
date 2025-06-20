#!/usr/bin/env python3
"""
Local development script for PokerBot
Runs the bot in polling mode instead of webhook mode
"""

import os
import logging
from dotenv import load_dotenv
from bot import bot, init_db

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function to run the bot locally"""
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")
        
        # Remove any existing webhook
        logger.info("Removing webhook...")
        bot.remove_webhook()
        
        # Start polling
        logger.info("Starting bot in polling mode...")
        logger.info("Bot is ready! Send /start to begin.")
        
        # Start polling (this will block until interrupted)
        bot.polling(none_stop=True, interval=0)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    main() 