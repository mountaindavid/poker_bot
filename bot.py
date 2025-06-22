# bot.py
import telebot
import os
import random
import psycopg2
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot setup
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMINS = [300526718, ]  # 7282197423
bot = telebot.TeleBot(TOKEN)
db_name = os.getenv("PGDATABASE", "railway")  # Fallback to 'railway' if PGDATABASE not set


def safe_handler(func):
    """safe command handler"""

    def wrapper(message):
        try:
            return func(message)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            bot.reply_to(message, f"❌ Error: {str(e)}")

    return wrapper


def _get_connection_params(database="pokerbot_dev"):
    """Extract connection parameters from DATABASE_URL or environment variables."""
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Parse DATABASE_URL (Railway/Heroku style)
        result = urlparse(database_url)
        return {
            'host': result.hostname,
            'port': result.port,
            'user': result.username,
            'password': result.password,
            'database': result.path[1:] if result.path else database,
            'sslmode': "require" if "railway" in result.hostname else "disable"
        }
    else:
        # Use individual environment variables (local development)
        return {
            'host': os.getenv("PGHOST", "localhost"),
            'port': os.getenv("PGPORT", "5432"),
            'user': os.getenv("PGUSER", "postgres"),
            'password': os.getenv("PGPASSWORD", "0000"),
            'database': database,
            'sslmode': "disable"
        }


def get_db_connection(database="pokerbot_dev"):
    """Get a database connection with autocommit enabled."""
    try:
        params = _get_connection_params(database)
        conn = psycopg2.connect(**params)
        conn.set_session(autocommit=True)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise


def init_db():
    """Initialize database and create required tables."""
    try:
        # Connect to postgres database to create target database
        params = _get_connection_params("postgres")
        target_db = _get_connection_params()['database']

        with psycopg2.connect(**params) as conn:
            conn.set_session(autocommit=True)
            with conn.cursor() as cursor:
                # Create database if it doesn't exist
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                if not cursor.fetchone():
                    cursor.execute(f"CREATE DATABASE {target_db}")
                    logger.info(f"Database {target_db} created")
                else:
                    logger.info(f"Database {target_db} already exists")

        # Connect to target database and create tables
        with get_db_connection(target_db) as conn:
            with conn.cursor() as cursor:
                logger.info("Creating tables...")

                # Create tables with proper constraints
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS players (
                        id SERIAL PRIMARY KEY,
                        telegram_id BIGINT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        total_buyin NUMERIC(10,1) DEFAULT 0.0,
                        total_cashout NUMERIC(10,1) DEFAULT 0.0,
                        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        games_played INTEGER DEFAULT 0
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS games (
                        id SERIAL PRIMARY KEY,
                        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE,
                        password TEXT,
                        creator_id BIGINT NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY,
                        player_id INTEGER NOT NULL,
                        game_id INTEGER NOT NULL,
                        amount NUMERIC(10,1) NOT NULL,
                        type TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
                        FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS game_players (
                        id SERIAL PRIMARY KEY,
                        player_id INTEGER NOT NULL,
                        game_id INTEGER NOT NULL,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
                        FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
                        UNIQUE(player_id, game_id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        id SERIAL PRIMARY KEY,
                        setting_name TEXT UNIQUE NOT NULL,
                        setting_value BOOLEAN NOT NULL DEFAULT FALSE
                    )
                ''')

                # Insert default settings
                cursor.execute('''
                    INSERT INTO settings (setting_name, setting_value) 
                    VALUES (%s, %s) 
                    ON CONFLICT (setting_name) DO NOTHING
                ''', ('allow_new_game', False))
                cursor.execute('''
                    INSERT INTO settings (setting_name, setting_value) 
                    VALUES (%s, %s) 
                    ON CONFLICT (setting_name) DO NOTHING
                ''', ('send_notifications', True))  # Default to True for notifications

                # Add total_rebuys column if it doesn't exist
                cursor.execute('''
                    ALTER TABLE players ADD COLUMN IF NOT EXISTS total_rebuys NUMERIC(10,1) DEFAULT 0.0
                ''')
                
                # Update total_rebuys from existing transactions
                cursor.execute('''
                    UPDATE players 
                    SET total_rebuys = COALESCE(
                        (SELECT SUM(amount) FROM transactions 
                         WHERE transactions.player_id = players.id AND transactions.type = 'rebuy'), 
                        0.0
                    )
                ''')

                logger.info("Database initialized successfully")

        # Run migrations to update schema
        try:
            from migrations import run_all_migrations
            logger.info("Running database migrations...")
            run_all_migrations()
            logger.info("Migrations completed successfully")
        except ImportError:
            logger.warning("Migrations module not found, skipping migrations")
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            # Don't raise here, as the basic tables are already created

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


# @bot.message_handler(commands=['menu'])
# @safe_handler
# def help_command(message):
#     keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
#     keyboard.row('/new_game', '/join')
#     keyboard.row('/rebuy', '/cashout')
#     keyboard.row('/leave', '/end_game')
#     keyboard.row('/game_results', '/admin')

#     bot.send_message(message.chat.id, "🃏 Tap a command to execute:", reply_markup=keyboard)


@bot.message_handler(commands=['admin'])
@safe_handler
def show_admin_commands(message):
    admin_commands = """
    Admin commands:
    /remove_player — Remove a player from the current game
    /adjust — Adjust buy-in, rebuy, cashout, or clear for a player
    /allow_new_game - Any player can create a new game
    /rename_player - Change player name in DB
    /notifications_switcher - Toggle notifications for all players

    /overall_results — Show overall results across all games
    /avg_profit — Show average profit per game

    /DELETE_DB - Delete everything
    """
    bot.reply_to(message, admin_commands)


# Player registration
@bot.message_handler(commands=['start'])
@safe_handler
def register(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO players (telegram_id, name) VALUES (%s, %s) ON CONFLICT (telegram_id) DO NOTHING",
              (user_id, name))
    conn.commit()
    conn.close()
    bot.reply_to(message,
                 f"{name}, you are registered!\n\n"
                 f"Open Menu and start playing!"
                 )
    logger.info(f"Player {name} (Telegram ID: {user_id}) registered")


# New game
@bot.message_handler(commands=['new_game'])
@safe_handler
def new_game(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    c = conn.cursor()

    # Check if user is registered
    c.execute("SELECT id, name FROM players WHERE telegram_id = %s", (user_id,))
    player = c.fetchone()
    if not player:
        bot.reply_to(message, "❌ You are not registered. Use /start.")
        conn.close()
        return
    creator_name = player[1]

    # Check allow_new_game setting
    c.execute("SELECT setting_value FROM settings WHERE setting_name = %s", ('allow_new_game',))
    allow_new_game = c.fetchone()
    allow_new_game = allow_new_game[0] if allow_new_game else False

    # If setting is False, only allow admins to create games
    if not allow_new_game and user_id not in ADMINS:
        bot.reply_to(message, "❌ Temporary unavailable.")
        conn.close()
        return

    # Check for active game
    c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
    active_game = c.fetchone()
    if active_game:
        bot.reply_to(message, f"❌ Game #{active_game[0]} is already active. End it first with /end_game.")
        conn.close()
        return

    bot.reply_to(message, "Enter a 4-digit password for the game:")
    bot.register_next_step_handler(message, lambda m: process_game_password(m, creator_name))
    conn.close()
    logger.info(f"User {creator_name} (Telegram ID: {user_id}) initiated new game creation")


# End game
@bot.message_handler(commands=['end_game'])
@safe_handler
def end_game(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    c = conn.cursor()
    # Get active game ID and creator info
    c.execute(
        "SELECT g.id, g.creator_id, p.name FROM games g JOIN players p ON g.creator_id = p.telegram_id WHERE g.is_active = TRUE ORDER BY g.id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id, creator_id, creator_name = game
    if user_id != creator_id and user_id != 300526718:
        bot.reply_to(message, f"❌ Only the game creator ({creator_name}) can end the game.")
        conn.close()
        return
    # End game
    c.execute("UPDATE games SET is_active = FALSE WHERE is_active = TRUE")
    conn.commit()
    bot.reply_to(message, f"Game #{game_id} ended.")
    notify_game_players(game_id, f"🏁 Game #{game_id} has ended by {creator_name}!", exclude_telegram_id=user_id)
    conn.close()
    logger.info(f"Game #{game_id} ended by {creator_name} (Telegram ID: {user_id})")


def process_game_password(message, creator_name):
    try:
        password = message.text.strip()
        if not (password.isdigit() and len(password) == 4):
            raise ValueError("Password must be 4 digits. /new_game")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO games (date, is_active, password, creator_id) VALUES (%s, TRUE, %s, %s) RETURNING id",
                  (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), password, message.from_user.id))
        game_id = c.fetchone()[0]
        conn.commit()
        bot.reply_to(message, f"Game #{game_id} created with password {password}!")
        notify_all_players_new_game(game_id, creator_name)
        conn.close()
        logger.info(f"Game #{game_id} created by {creator_name} with password {password}")
    except Exception as e:
        print("Error creating game:", e)
        bot.reply_to(message, "❌ Enter a valid 4-digit password. /new_game")
        logger.error(f"Error creating game for {creator_name}: {e}")


@bot.message_handler(commands=['join'])
@safe_handler
def join_game(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = get_db_connection()
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    c = conn.cursor()
    # Check if player is registered
    c.execute("SELECT id FROM players WHERE telegram_id = %s", (user_id,))
    player = c.fetchone()
    if not player:
        bot.reply_to(message, "❌ You are not registered. Use /start.")
        conn.close()
        return
    player_id = player[0]
    # Check active game
    c.execute("SELECT id, password FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game. Create a /new_game")
        conn.close()
        return
    game_id, password = game
    bot.reply_to(message, f"{name}, enter the 4-digit password for game #{game_id}:")
    bot.register_next_step_handler(message, lambda m: process_join_password(m, game_id, password, player_id, name))
    conn.close()
    logger.info(f"Player {name} (Telegram ID: {user_id}) initiated joining game #{game_id}")


def process_join_password(message, game_id, correct_password, player_id, name):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        password = message.text.strip()
        if password != correct_password:
            bot.reply_to(message, "❌ Incorrect password. Try to /join again")
            return
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        if c.fetchone():
            bot.reply_to(message, f"{suits}{name}, you are already in game #{game_id}.")
            conn.close()
            return
        bot.reply_to(message, f"{suits}{name}, enter buy-in, USD (example 20):")
        bot.register_next_step_handler(message, lambda m: process_buyin(m, name, game_id, player_id))
        conn.close()
        logger.info(f"Player {name} (ID: {player_id}) passed password check for game #{game_id}")
    except Exception as e:
        print("Error joining game:", e)
        bot.reply_to(message, "❌ Try to /join again.")
        logger.error(f"Error joining game #{game_id} for {name}: {e}")


def process_buyin(message, name, game_id, player_id):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount_text = message.text.strip()
        print(f"DEBUG: amount_text = '{amount_text}'")
        amount = round(float(amount_text), 1)
        print(f"DEBUG: amount = {amount}")
        if not (amount > 0 and amount <= 5000):
            raise ValueError("Amount must be from 1 to 5000 (example 20).")
        user_id = message.from_user.id
        print(f"DEBUG: user_id = {user_id}, game_id = {game_id}, player_id = {player_id}")

        conn = get_db_connection()
        c = conn.cursor()

        # Verify that the game is still active
        c.execute("SELECT id FROM games WHERE id = %s AND is_active = TRUE", (game_id,))
        game_check = c.fetchone()
        print(f"DEBUG: game_check = {game_check}")
        if not game_check:
            bot.reply_to(message, "❌ Game is no longer active. /join or create a /new_game")
            conn.close()
            return

        # Check if already joined
        c.execute("SELECT id FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        already_joined = c.fetchone()
        print(f"DEBUG: already_joined = {already_joined}")
        
        if not already_joined:
            # Add player to game and increment games_played only if not already joined
            c.execute("INSERT INTO game_players (player_id, game_id) VALUES (%s, %s) ON CONFLICT (player_id, game_id) DO NOTHING", (player_id, game_id))
            c.execute("UPDATE players SET games_played = games_played + 1 WHERE id = %s", (player_id,))

        # Save the buy-in transaction (amount is negative)
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                  (player_id, game_id, -amount, 'buyin'))

        # Update total buy-in
        c.execute("UPDATE players SET total_buyin = total_buyin + %s WHERE id = %s", (amount, player_id))

        conn.commit()
        
        if already_joined:
            bot.reply_to(message, f"✅ {name} added a buy-in of {amount:.1f}{suits} to game #{game_id}.")
            notify_game_players(game_id, f"💰 {name} added a buy-in of {amount:.1f}{suits} to game #{game_id}!",
                                exclude_telegram_id=user_id)
            logger.info(f"Player {name} (ID: {player_id}) added buy-in of {amount:.1f} to game #{game_id}")
        else:
            bot.reply_to(message, f"✅ {name} has joined game #{game_id} with a buy-in of {amount:.1f}{suits}.")
            notify_game_players(game_id, f"👤 {name} joined game #{game_id} with a buy-in of {amount:.1f}{suits}!",
                                exclude_telegram_id=user_id)
            logger.info(f"Player {name} (ID: {player_id}) joined game #{game_id} with buy-in {amount:.1f}")
    except Exception as e:
        print(f"Error in buy-in process: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        bot.reply_to(message, "❌ Try to /join again. Enter number like 20")
        logger.error(f"Error processing buy-in for {name} in game #{game_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Add rebuy
@bot.message_handler(commands=['rebuy'])
@safe_handler
def rebuy(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = get_db_connection()
    c = conn.cursor()

    # Check active game
    c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id = game[0]

    # Check if player is registered
    c.execute("SELECT id FROM players WHERE telegram_id = %s", (user_id,))
    player = c.fetchone()
    if not player:
        bot.reply_to(message, "❌ You are not registered. Use /start.")
        conn.close()
        return
    player_id = player[0]

    # Check if player joined the active game
    c.execute("SELECT id FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
    if not c.fetchone():
        bot.reply_to(message, "You should /join to the current game")
        conn.close()
        return

    bot.reply_to(message, "Enter the rebuy amount (example 50.5)")
    bot.register_next_step_handler(message, lambda m: process_rebuy(m, name, game_id, player_id))
    conn.close()
    logger.info(f"Player {name} (Telegram ID: {user_id}) initiated rebuy for game #{game_id}")


def process_rebuy(message, name, game_id, player_id):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount = round(float(message.text.strip()), 1)
        if not (amount > 0 and amount <= 5000):
            raise ValueError("Amount must be from 1 to 5000 (example 20.5).")
        user_id = message.from_user.id

        conn = get_db_connection()
        c = conn.cursor()

        # Verify that the game is still active
        c.execute("SELECT id FROM games WHERE id = %s AND is_active = TRUE", (game_id,))
        if not c.fetchone():
            bot.reply_to(message, "❌ Game is no longer active.")
            conn.close()
            return

        # Insert rebuy record
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                  (player_id, game_id, -amount, 'rebuy'))

        # Update total rebuys (not total_buyin)
        c.execute("UPDATE players SET total_rebuys = total_rebuys + %s WHERE id = %s", (amount, player_id))

        conn.commit()
        bot.reply_to(message, f"✅ {name} made a rebuy of {amount:.1f}{suits} in game #{game_id}.")
        notify_game_players(game_id, f"💸 {name} made a rebuy of {amount:.1f}{suits} in game #{game_id}!",
                            exclude_telegram_id=user_id)
        logger.info(f"Player {name} (ID: {player_id}) made rebuy of {amount:.1f} in game #{game_id}")
    except Exception as e:
        print("Error in rebuy:", e)
        bot.reply_to(message, "❌ Try to /rebuy again. Number up to 5000 (example 20.5)")
        logger.error(f"Error processing rebuy for {name} in game #{game_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Add cashout
@bot.message_handler(commands=['cashout'])
@safe_handler
def cashout(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = get_db_connection()
    c = conn.cursor()

    # Check active game
    c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game session.")
        conn.close()
        return
    game_id = game[0]

    # Check if player is registered
    c.execute("SELECT id FROM players WHERE telegram_id = %s", (user_id,))
    player = c.fetchone()
    if not player:
        bot.reply_to(message, "❌ You are not registered. Use /start.")
        conn.close()
        return
    player_id = player[0]

    # Check if player joined the active game
    c.execute("SELECT id FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
    if not c.fetchone():
        bot.reply_to(message, "You should join to the current game")
        conn.close()
        return

    bot.reply_to(message, "Enter cashout amount (example 11.4)")
    bot.register_next_step_handler(message, lambda m: process_cashout(m, name, game_id, player_id))
    conn.close()
    logger.info(f"Player {name} (Telegram ID: {user_id}) initiated cashout for game #{game_id}")


def process_cashout(message, name, game_id, player_id):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount = round(float(message.text.strip()), 1)
        if not (amount > 0 and amount <= 5000):
            raise ValueError("Amount must be from 1 to 5000 (example 20.5).")
        user_id = message.from_user.id

        conn = get_db_connection()
        c = conn.cursor()

        # Verify that the game is still active
        c.execute("SELECT id FROM games WHERE id = %s AND is_active = TRUE", (game_id,))
        if not c.fetchone():
            bot.reply_to(message, "❌ Game is no longer active.")
            conn.close()
            return

        # Save cashout
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                  (player_id, game_id, amount, 'cashout'))

        # Update total cashout
        c.execute("UPDATE players SET total_cashout = total_cashout + %s WHERE id = %s", (amount, player_id))

        conn.commit()
        bot.reply_to(message, f"✅ {name} cashed out {amount:.1f}{suits} in game #{game_id}.")
        notify_game_players(game_id, f"💰 {name} cashed out {amount:.1f}{suits} in game #{game_id}!",
                            exclude_telegram_id=user_id)
        logger.info(f"Player {name} (ID: {player_id}) cashed out {amount:.1f} in game #{game_id}")
    except Exception as e:
        print("Cashout error:", e)
        bot.reply_to(message, "❌ Try to /cashout again. Number from 1 to 5000 (example 20.5)")
        logger.error(f"Error processing cashout for {name} in game #{game_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


@bot.message_handler(commands=['leave'])
@safe_handler
def reset(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id = game[0]
    c.execute("SELECT id FROM players WHERE telegram_id = %s", (user_id,))
    player = c.fetchone()
    if not player:
        bot.reply_to(message, "❌ You are not registered. Use /start.")
        conn.close()
        return
    player_id = player[0]
    c.execute("SELECT id FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
    if not c.fetchone():
        bot.reply_to(message, "❌ You are not in the current game.")
        conn.close()
        return
    c.execute("SELECT password FROM games WHERE id = %s", (game_id,))
    password = c.fetchone()[0]
    bot.reply_to(message, f"{name}, enter game pass, your data will be deleted in game #{game_id}:")
    bot.register_next_step_handler(message, lambda m: process_reset_password(m, game_id, password, player_id, name))
    conn.close()
    logger.info(f"Player {name} (Telegram ID: {user_id}) initiated leaving for game #{game_id}")


def process_reset_password(message, game_id, correct_password, player_id, name):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        password = message.text.strip()
        if password != correct_password:
            bot.reply_to(message, "❌ Incorrect password. Try to /leave again.")
            return
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT amount, type FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        transactions = c.fetchall()
        for amount, trans_type in transactions:
            if trans_type == 'buyin':
                c.execute("UPDATE players SET total_buyin = total_buyin - %s WHERE id = %s", (-amount, player_id))
            elif trans_type == 'rebuy':
                c.execute("UPDATE players SET total_rebuys = total_rebuys - %s WHERE id = %s", (-amount, player_id))
            elif trans_type == 'cashout':
                c.execute("UPDATE players SET total_cashout = total_cashout - %s WHERE id = %s",
                          (amount, player_id))
        c.execute("DELETE FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        c.execute("DELETE FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        c.execute("UPDATE players SET games_played = games_played - 1 WHERE id = %s", (player_id,))
        conn.commit()
        bot.reply_to(message, f"✅ {name} left game #{game_id}{suits}.")
        notify_game_players(game_id, f"🔄 {name} left game #{game_id}{suits}!", exclude_telegram_id=message.from_user.id)
        logger.info(f"Player {name} (ID: {player_id}) left from game #{game_id}")
    except Exception as e:
        print("Error in leaving process:", e)
        bot.reply_to(message, "❌ Try to /leave again.")
        logger.error(f"Error leaving game #{game_id} for {name}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# game results
@bot.message_handler(commands=['game_results'])
@safe_handler
def game_results(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    c = conn.cursor()

    # search active game
    c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()

    if row:
        # show results
        active_game_id = row[0]
        send_game_results_to_user(active_game_id, message.chat.id)
    else:
        # if no current game - ender previous game ID
        bot.reply_to(message, "⚠️ No active game. Enter the game number to view past results:")
        bot.register_next_step_handler(message, process_game_results)
    logger.info(f"User (Telegram ID: {user_id}) requested game results")


def process_game_results(message):
    try:
        game_id = int(message.text.strip())
        send_game_results_to_user(game_id, message.chat.id)
        logger.info(f"User requested results for game #{game_id}")
    except Exception as e:
        print("Game results error:", e)
        bot.reply_to(message, "❌ Try to see /game_results again with correct game ID.")
        logger.error(f"Error processing game results for game #{message.text}: {e}")


def send_game_results_to_user(game_id, chat_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.name, 
               SUM(CASE WHEN t.type = 'buyin' THEN -t.amount ELSE 0 END) as buyins,
               SUM(CASE WHEN t.type = 'rebuy' THEN -t.amount ELSE 0 END) as rebuys,
               SUM(CASE WHEN t.type = 'cashout' THEN t.amount ELSE 0 END) as cashouts,
               CAST(SUM(t.amount) AS NUMERIC(10,1)) as total
        FROM transactions t
        JOIN players p ON t.player_id = p.id
        WHERE t.game_id = %s
        GROUP BY p.id
    """, (game_id,))
    results = c.fetchall()
    conn.close()

    if not results:
        bot.send_message(chat_id, f"⚠️ No data found for game #{game_id}.")
        return

    response = f"♠️ Game #{game_id} results:\n\n"

    total_buyins = 0
    total_rebuys = 0
    total_cashouts = 0

    for player_id, name, buyins, rebuys, cashouts, total in results:
        total_buyins += buyins
        total_rebuys += rebuys
        total_cashouts += cashouts
        response += (
            f"{name}: Buy-in: {buyins:.1f}, Rebuy: {rebuys:.1f}, "
            f"Cashout: {cashouts:.1f}, Total: {'+' if total > 0 else ''}{total:.1f}\n"
        )

    total_in = total_buyins + total_rebuys
    total_out = total_cashouts
    diff = round(total_in - total_out, 1)

    response += (
        f"\n💰 Game total:\n"
        f"  Buy-ins + Rebuys = {total_in:.1f}\n"
        f"  Cashouts = {total_out:.1f}\n"
        f"  Difference = {diff:.1f} {'✅ OK — balanced' if diff == 0 else ''}"
    )

    bot.send_message(chat_id, response)


# Overall results
@bot.message_handler(commands=['overall_results'])
@safe_handler
def overall_results(message):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get basic player stats with player IDs
    c.execute("""
                SELECT p.id, p.name, 
                       p.games_played, 
                       CAST(
                           COALESCE(SUM(CASE WHEN t.type = 'buyin' THEN ABS(t.amount) ELSE 0 END), 0) AS NUMERIC(10,1)
                       ) as total_buyins,
                       CAST(
                           COALESCE(SUM(CASE WHEN t.type = 'rebuy' THEN ABS(t.amount) ELSE 0 END), 0) AS NUMERIC(10,1)
                       ) as total_rebuys,
                       CAST(
                           COALESCE(SUM(CASE WHEN t.type = 'cashout' THEN t.amount ELSE 0 END), 0) AS NUMERIC(10,1)
                       ) as total_cashouts
                FROM players p
                LEFT JOIN transactions t ON t.player_id = p.id
                GROUP BY p.id, p.name, p.games_played
                ORDER BY p.name
            """)
    players = c.fetchall()
    
    # Get win rates for all players
    c.execute("""
        SELECT player_id, 
               COUNT(DISTINCT game_id) as total_games,
               COUNT(DISTINCT CASE WHEN game_profit > 0 THEN game_id END) as winning_games
        FROM (
            SELECT player_id, game_id,
                   SUM(CASE WHEN type = 'cashout' THEN amount ELSE 0 END) - 
                   SUM(CASE WHEN type IN ('buyin', 'rebuy') THEN ABS(amount) ELSE 0 END) as game_profit
            FROM transactions 
            GROUP BY player_id, game_id
        ) game_stats
        GROUP BY player_id
    """)
    win_rates = {row[0]: (row[1], row[2]) for row in c.fetchall()}
    
    # Get bank statistics for all games
    c.execute("""
        SELECT 
            MAX(total_bank) as max_bank,
            AVG(total_bank) as avg_bank
        FROM (
            SELECT game_id,
                   SUM(CASE WHEN type IN ('buyin', 'rebuy') THEN ABS(amount) ELSE 0 END) as total_bank
            FROM transactions 
            GROUP BY game_id
        ) game_banks
    """)
    bank_stats = c.fetchone()
    max_bank = bank_stats[0] if bank_stats[0] else 0
    avg_bank = bank_stats[1] if bank_stats[1] else 0
    
    conn.close()

    if not players:
        bot.reply_to(message, "No player data found.")
        return

    # Create table header
    response = "📊 Overall Results:\n"
    response += f"{'Name':<15} | {'Games':<8} | {'Total $':<10} | {'Win Rate':<12} | {'Avg/Game':<10}\n"
    response += "-" * 70 + "\n"

    # Fill table rows
    for player_id, name, games_played, player_buyins, player_rebuys, player_cashouts in players:
        # Calculate actual profit from transactions
        actual_profit = player_cashouts - (player_buyins + player_rebuys)
        
        # Get win rate
        win_rate = "N/A"
        if player_id in win_rates:
            total_games, winning_games = win_rates[player_id]
            if total_games > 0:
                win_rate = f"{winning_games/total_games*100:.0f}%"
        
        # Calculate average profit per game
        avg_profit = actual_profit / games_played if games_played > 0 else 0
        
        # Truncate name to 15 characters
        name = name[:15]
        # Format actual_profit to ensure consistent width
        profit_str = f"{'+' if actual_profit > 0 else ''}{actual_profit:.1f}"
        avg_str = f"{'+' if avg_profit > 0 else ''}{avg_profit:.1f}"
        response += f"{name:<15} | {games_played:<8} | {profit_str:<10} | {win_rate:<12} | {avg_str:<10}\n"

    # Add bank statistics
    response += f"\n💰 Bank Statistics:\n"
    response += f"  Max Bank: {max_bank:.1f}\n"
    response += f"  Avg Bank: {avg_bank:.1f}"

    bot.send_message(message.chat.id, response)


# average profit per game
@bot.message_handler(commands=['avg_profit'])
@safe_handler
def avg_profit(message):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.name, CAST(AVG(s.total) AS NUMERIC(10,1))
        FROM (
            SELECT player_id, game_id, SUM(amount) as total
            FROM transactions
            GROUP BY player_id, game_id
        ) s
        JOIN players p ON s.player_id = p.id
        GROUP BY p.id
    """)
    results = c.fetchall()
    conn.close()
    response = "Average profit per game:\n"
    for name, avg in results:
        response += f"{name}: {'+' if avg > 0 else ''}{avg:.1f}\n"
    bot.reply_to(message, response)
    logger.info(f"User (Telegram ID: {message.from_user.id}) requested average profit")


# ADMINS
@bot.message_handler(commands=['remove_player'])
@safe_handler
def remove_player(message):
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "❌ Access denied! Admins only.")
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id = game[0]
    c.execute("SELECT p.id, p.name FROM players p JOIN game_players gp ON p.id = gp.player_id WHERE gp.game_id = %s",
              (game_id,))
    players = c.fetchall()
    if not players:
        bot.reply_to(message, "❌ No players in the current game.")
        conn.close()
        return
    keyboard = telebot.types.InlineKeyboardMarkup()
    for player_id, name in players:
        keyboard.add(telebot.types.InlineKeyboardButton(text=name, callback_data=f"remove_{game_id}_{player_id}"))
    bot.reply_to(message, f"Select a player to remove from game #{game_id}:", reply_markup=keyboard)
    conn.close()
    logger.info(f"Admin (Telegram ID: {message.from_user.id}) initiated player removal for game #{game_id}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
@safe_handler
def handle_remove_player_callback(call):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        _, game_id, player_id = call.data.split('_')
        game_id = int(game_id)
        player_id = int(player_id)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM players WHERE id = %s", (player_id,))
        player = c.fetchone()
        if not player:
            bot.answer_callback_query(call.id, "Invalid player ID.")
            conn.close()
            return
        name = player[0]
        c.execute("SELECT id FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        if not c.fetchone():
            bot.answer_callback_query(call.id, f"{name} is not in game #{game_id}.")
            conn.close()
            return
        c.execute("SELECT amount, type FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        transactions = c.fetchall()
        for amount, trans_type in transactions:
            if trans_type == 'buyin':
                c.execute("UPDATE players SET total_buyin = total_buyin - %s WHERE id = %s", (-amount, player_id))
            elif trans_type == 'rebuy':
                c.execute("UPDATE players SET total_rebuys = total_rebuys - %s WHERE id = %s", (-amount, player_id))
            elif trans_type == 'cashout':
                c.execute("UPDATE players SET total_cashout = total_cashout - %s WHERE id = %s",
                          (amount, player_id))
        c.execute("DELETE FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        c.execute("DELETE FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        c.execute("UPDATE players SET games_played = games_played - 1 WHERE id = %s", (player_id,))
        conn.commit()
        bot.answer_callback_query(call.id, f"{name} removed from game #{game_id}{suits}.")
        bot.edit_message_text(f"✅ {name} removed from game #{game_id}{suits}.", call.message.chat.id,
                              call.message.message_id)
        notify_game_players(game_id, f"🚪 {name} removed from game #{game_id}{suits}!", exclude_telegram_id=None)
        logger.info(f"Admin removed player {name} (ID: {player_id}) from game #{game_id}")
    except Exception as e:
        print("Error in remove_player callback:", e)
        bot.answer_callback_query(call.id, "Error removing player.")
        logger.error(f"Error removing player ID {player_id} from game #{game_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Add new adjust function
@bot.message_handler(commands=['adjust'])
@safe_handler
def adjust(message):
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "❌ Access denied! Admins only.")
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id = game[0]
    c.execute("SELECT p.id, p.name FROM players p JOIN game_players gp ON p.id = gp.player_id WHERE gp.game_id = %s",
              (game_id,))
    players = c.fetchall()
    if not players:
        bot.reply_to(message, "❌ No players in the current game.")
        conn.close()
        return
    keyboard = telebot.types.InlineKeyboardMarkup()
    for player_id, name in players:
        keyboard.add(telebot.types.InlineKeyboardButton(text=name, callback_data=f"adjust_{game_id}_{player_id}"))
    bot.reply_to(message, f"Select a player to adjust in game #{game_id}:", reply_markup=keyboard)
    conn.close()
    logger.info(f"Admin (Telegram ID: {message.from_user.id}) initiated adjustment for game #{game_id}")


# Add callback handler for player selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('adjust_'))
@safe_handler
def handle_adjust_player_callback(call):
    try:
        _, game_id, player_id = call.data.split('_')
        game_id = int(game_id)
        player_id = int(player_id)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM players WHERE id = %s", (player_id,))
        player = c.fetchone()
        if not player:
            bot.answer_callback_query(call.id, "Invalid player ID.")
            conn.close()
            return
        name = player[0]
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.row(
            telebot.types.InlineKeyboardButton(text="Rebuy", callback_data=f"rebuy_{game_id}_{player_id}"),
            telebot.types.InlineKeyboardButton(text="Cashout", callback_data=f"cashout_{game_id}_{player_id}")
        )
        keyboard.add(telebot.types.InlineKeyboardButton(text="Clear", callback_data=f"clear_{game_id}_{player_id}"))
        bot.edit_message_text(f"Adjust for {name} in game #{game_id}:", call.message.chat.id, call.message.message_id,
                              reply_markup=keyboard)
        logger.info(f"Admin selected player {name} (ID: {player_id}) for adjustment in game #{game_id}")
    except Exception as e:
        print("Error in adjust player callback:", e)
        bot.answer_callback_query(call.id, "Error selecting player.")
        logger.error(f"Error selecting player ID {player_id} for adjustment in game #{game_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Add callback handler for rebuy, cashout, and clear actions
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rebuy_', 'cashout_', 'clear_')))
@safe_handler
def handle_adjust_action_callback(call):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        action, game_id, player_id = call.data.split('_')
        game_id = int(game_id)
        player_id = int(player_id)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM players WHERE id = %s", (player_id,))
        player = c.fetchone()
        if not player:
            bot.answer_callback_query(call.id, "Invalid player ID.")
            conn.close()
            return
        name = player[0]
        c.execute("SELECT id FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        if not c.fetchone():
            bot.answer_callback_query(call.id, f"{name} is not in game #{game_id}.")
            conn.close()
            return
        if action == 'clear':
            c.execute("SELECT amount, type FROM transactions WHERE player_id = %s AND game_id = %s",
                      (player_id, game_id))
            transactions = c.fetchall()
            for amount, trans_type in transactions:
                if trans_type == 'buyin':
                    c.execute("UPDATE players SET total_buyin = total_buyin - %s WHERE id = %s", (-amount, player_id))
                elif trans_type == 'rebuy':
                    c.execute("UPDATE players SET total_rebuys = total_rebuys - %s WHERE id = %s", (-amount, player_id))
                elif trans_type == 'cashout':
                    c.execute("UPDATE players SET total_cashout = total_cashout - %s WHERE id = %s",
                              (amount, player_id))
            c.execute("DELETE FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
            c.execute("DELETE FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
            c.execute("UPDATE players SET games_played = games_played - 1 WHERE id = %s", (player_id,))
            conn.commit()
            bot.answer_callback_query(call.id, f"{name}'s transactions cleared in game #{game_id}{suits}.")
            bot.edit_message_text(f"✅ {name}'s transactions and participation in game #{game_id} cleared{suits}.",
                                  call.message.chat.id, call.message.message_id)
            notify_game_players(game_id, f"🔄 {name} left game #{game_id}{suits}!", exclude_telegram_id=None)
            logger.info(f"Admin cleared transactions for player {name} (ID: {player_id}) in game #{game_id}")
        else:
            action_type = 'rebuy' if action == 'rebuy' else 'cashout'
            bot.edit_message_text(
                f"Enter {action_type} amount for {name} in game #{game_id} (Positive number up to 5000, example 20.5):",
                call.message.chat.id, call.message.message_id)
            bot.register_next_step_handler_by_chat_id(call.message.chat.id,
                                                      lambda m: process_adjust_amount(m, game_id, player_id,
                                                                                      action_type, name))
            logger.info(
                f"Admin initiated {action_type} adjustment for player {name} (ID: {player_id}) in game #{game_id}")
    except Exception as e:
        print(f"Error in {action} callback:", e)
        bot.answer_callback_query(call.id, f"Error processing {action}.")
        logger.error(f"Error processing {action} for player ID {player_id} in game #{game_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Add function to process rebuy or cashout amount
def process_adjust_amount(message, game_id, player_id, action_type, name):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount = round(float(message.text.strip()), 1)
        if not (amount > 0 and amount <= 5000):
            raise ValueError("Amount must be from 1 to 5000 (example 20.5).")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM games WHERE id = %s AND is_active = TRUE", (game_id,))
        if not c.fetchone():
            bot.reply_to(message, "❌ No active game found.")
            conn.close()
            return
        c.execute("SELECT id FROM players WHERE id = %s", (player_id,))
        if not c.fetchone():
            bot.reply_to(message, "❌ Invalid player ID.")
            conn.close()
            return
        amount_value = -amount if action_type == 'rebuy' else amount
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                  (player_id, game_id, amount_value, action_type))
        if action_type == 'rebuy':
            c.execute("UPDATE players SET total_rebuys = total_rebuys + %s WHERE id = %s", (amount, player_id))
        else:
            c.execute("UPDATE players SET total_cashout = total_cashout + %s WHERE id = %s", (amount, player_id))
        conn.commit()
        bot.reply_to(message, f"✅ {name} {action_type} of {amount:.1f}{suits} in game #{game_id}.")
        notification_text = f"💸 {name} rebuy of {amount:.1f}{suits} in game #{game_id}!" if action_type == 'rebuy' else f"💰 {name} cashed out {amount:.1f}{suits} in game #{game_id}!"
        notify_game_players(game_id, notification_text, exclude_telegram_id=None)
        logger.info(
            f"Admin processed {action_type} of {amount:.1f} for player {name} (ID: {player_id}) in game #{game_id}")
    except Exception as e:
        print(f"Error in {action_type} amount processing:", e)
        bot.reply_to(message, f"❌ Try again. Number from 1 to 5000 (example 20.5)")
        logger.error(f"Error processing {action_type} amount for player {name} in game #{game_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


@bot.message_handler(commands=['allow_new_game'])
@safe_handler
def allow_new_game(message):
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "❌ Access denied! Admins only.")
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT setting_value FROM settings WHERE setting_name = %s", ('allow_new_game',))
    current_setting = c.fetchone()
    current_setting = current_setting[0] if current_setting else False
    new_setting = not current_setting
    c.execute("UPDATE settings SET setting_value = %s WHERE setting_name = %s", (new_setting, 'allow_new_game'))
    conn.commit()
    status = "enabled" if new_setting else "disabled"
    bot.reply_to(message, f"✅ Creating new games for all registered players is now {status}.")
    conn.close()
    logger.info(f"Admin (Telegram ID: {message.from_user.id}) set allow_new_game to {status}")


# Handler for admin command to rename a player
@bot.message_handler(commands=['rename_player'])
@safe_handler
def rename_player(message):
    """Initiate player renaming process for admins."""
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "❌ Access denied! Admins only.")
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM players")
    players = c.fetchall()
    if not players:
        bot.reply_to(message, "❌ No players found.")
        conn.close()
        return
    keyboard = telebot.types.InlineKeyboardMarkup()
    for player_id, name in players:
        keyboard.add(telebot.types.InlineKeyboardButton(text=name, callback_data=f"rename_{player_id}"))
    bot.reply_to(message, "Select a player to rename:", reply_markup=keyboard)
    conn.close()
    logger.info(f"Admin (Telegram ID: {message.from_user.id}) initiated player renaming")


# Callback handler for selecting a player to rename
@bot.callback_query_handler(func=lambda call: call.data.startswith('rename_'))
@safe_handler
def handle_rename_player_callback(call):
    """Handle player selection for renaming."""
    try:
        _, player_id = call.data.split('_')
        player_id = int(player_id)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM players WHERE id = %s", (player_id,))
        player = c.fetchone()
        if not player:
            bot.answer_callback_query(call.id, "Invalid player ID.")
            conn.close()
            return
        name = player[0]
        bot.edit_message_text(f"Enter new name for {name}:", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, lambda m: process_rename(m, player_id, name))
        logger.info(f"Admin selected player {name} (ID: {player_id}) for renaming")
    except Exception as e:
        print("Error in rename player callback:", e)
        bot.answer_callback_query(call.id, "Error selecting player.")
        logger.error(f"Error selecting player ID {player_id} for renaming: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Process the new name for the player
def process_rename(message, player_id, old_name):
    """Update player's name in the database."""
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        new_name = message.text.strip()
        if not new_name:
            raise ValueError("Name cannot be empty.")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM players WHERE id = %s", (player_id,))
        if not c.fetchone():
            bot.reply_to(message, "❌ Invalid player ID.")
            conn.close()
            return
        c.execute("UPDATE players SET name = %s WHERE id = %s", (new_name, player_id))
        conn.commit()
        bot.reply_to(message, f"✅ Player {old_name} renamed to {new_name}{suits}.")
        logger.info(f"Admin renamed player {old_name} (ID: {player_id}) to {new_name}")
    except Exception as e:
        print("Error in rename processing:", e)
        bot.reply_to(message, "❌ Try again with a valid name.")
        logger.error(f"Error renaming player ID {player_id} from {old_name}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Notify all registered players about a new game
def notify_all_players_new_game(game_id, creator_name):
    """Send notification to all registered players about new game creation."""
    if not are_notifications_enabled():
        logger.info(f"Notifications disabled, skipping new game #{game_id} notification")
        return
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT telegram_id FROM players")
        players = c.fetchall()
        for player in players:
            telegram_id = player[0]
            try:
                bot.send_message(telegram_id, f"🎲 New game #{game_id} has been created by {creator_name}!")
            except Exception as e:
                logger.error(f"Failed to notify player {telegram_id} about new game #{game_id}: {e}")
        logger.info(f"Notified all players about new game #{game_id} created by {creator_name}")
    except Exception as e:
        logger.error(f"Error notifying players about new game #{game_id}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Notify all game participants about an action
def notify_game_players(game_id, message_text, exclude_telegram_id=None):
    """Send notification to all players in the specified game, excluding the specified telegram_id if provided."""
    if not are_notifications_enabled():
        logger.info(f"Notifications disabled, skipping notification for game #{game_id}: {message_text}")
        return
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            SELECT p.telegram_id 
            FROM players p 
            JOIN game_players gp ON p.id = gp.player_id 
            WHERE gp.game_id = %s
        """, (game_id,))
        players = c.fetchall()
        for player in players:
            telegram_id = player[0]
            if exclude_telegram_id and telegram_id == exclude_telegram_id:
                continue
            try:
                bot.send_message(telegram_id, message_text)
            except Exception as e:
                logger.error(f"Failed to notify player {telegram_id} for game #{game_id}: {e}")
        logger.info(f"Notified game #{game_id} players: {message_text}")
    except Exception as e:
        logger.error(f"Error notifying game #{game_id} players: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


def are_notifications_enabled():
    """Check the send_notifications setting in the database."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM settings WHERE setting_name = %s", ('send_notifications',))
        result = c.fetchone()
        conn.close()
        return result[0] if result else True  # Default to True if setting not found
    except Exception as e:
        logger.error(f"Error checking notifications setting: {e}")
        return True  # Default to True on error to maintain existing behavior


@bot.message_handler(commands=['notifications_switcher'])
@safe_handler
def notifications_switcher(message):
    """Toggle the send_notifications setting for all registered players."""
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "❌ Access denied! Admins only.")
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT setting_value FROM settings WHERE setting_name = %s", ('send_notifications',))
    current_setting = c.fetchone()
    current_setting = current_setting[0] if current_setting else True
    new_setting = not current_setting
    c.execute("UPDATE settings SET setting_value = %s WHERE setting_name = %s", (new_setting, 'send_notifications'))
    conn.commit()
    status = "enabled" if new_setting else "disabled"
    bot.reply_to(message, f"✅ Notifications {status}.")
    conn.close()
    logger.info(f"Admin (Telegram ID: {message.from_user.id}) set notifications to {status}")


# Handler for admin command to delete the database
@bot.message_handler(commands=['DELETE_DB'])
@safe_handler
def delete_db(message):
    """Initiate database deletion process for admins."""
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "❌ Access denied! Admins only.")
        return
    bot.reply_to(message, "Are you sure you want to delete the entire database? Type 'yes' to confirm:")
    bot.register_next_step_handler(message, process_delete_db_confirmation)
    logger.info(f"Admin (Telegram ID: {message.from_user.id}) initiated database deletion")


def process_delete_db_confirmation(message):
    """Process confirmation for database deletion."""
    try:
        confirmation = message.text.strip().lower()
        if confirmation != 'yes':
            bot.reply_to(message, "❌ Database deletion cancelled.")
            logger.info(f"Admin (Telegram ID: {message.from_user.id}) cancelled database deletion")
            return
        conn = get_db_connection()
        c = conn.cursor()
        # Drop all tables
        c.execute("DROP TABLE IF EXISTS transactions CASCADE")
        c.execute("DROP TABLE IF EXISTS game_players CASCADE")
        c.execute("DROP TABLE IF EXISTS games CASCADE")
        c.execute("DROP TABLE IF EXISTS players CASCADE")
        c.execute("DROP TABLE IF EXISTS settings CASCADE")
        conn.commit()
        conn.close()
        # Reinitialize the database
        init_db()
        bot.reply_to(message, "✅ Database cleared and reinitialized.")
        logger.info(f"Admin (Telegram ID: {message.from_user.id}) cleared and reinitialized the database")
    except Exception as e:
        print("Error in database deletion:", e)
        bot.reply_to(message, "❌ Error clearing database. Try again.")
        logger.error(f"Error clearing database for admin (Telegram ID: {message.from_user.id}): {e}")
    finally:
        if 'conn' in locals():
            conn.close()


# Start bot
if __name__ == '__main__':
    init_db()
    if not os.getenv("RAILWAY_ENVIRONMENT"):
        bot.remove_webhook()
        bot.polling()