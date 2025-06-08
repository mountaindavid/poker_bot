#bot.py
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
ADMINS = [300526718, ] #7282197423
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


# Initialize PostgreSQL database
def init_db():
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        # Parse DATABASE_URL
        result = urlparse(database_url)

        # Connect to default 'postgres' database to check/create target database
        conn = psycopg2.connect(
            host=result.hostname,
            port=result.port,
            user=result.username,
            password=result.password,
            database="postgres",  # Use system database
            sslmode="require"  # Railway requires SSL
        )
        conn.set_session(autocommit=True)
        c = conn.cursor()
        logger.info("Checking/creating database")

        # Extract database name from DATABASE_URL or use PGDATABASE
        target_db = result.path[1:] if result.path else db_name  # Remove leading '/'

        # Check if target database exists
        c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
        if not c.fetchone():
            c.execute(f"CREATE DATABASE {target_db}")
            logger.info(f"Database {target_db} created")
        else:
            logger.info(f"Database {target_db} already exists")
        conn.close()

        # Connect to target database
        conn = psycopg2.connect(
            host=result.hostname,
            port=result.port,
            user=result.username,
            password=result.password,
            database=target_db,
            sslmode="require"
        )
        conn.set_session(autocommit=True)
        c = conn.cursor()
        logger.info("Initializing tables in database")

        c.execute('''CREATE TABLE IF NOT EXISTS players (
                         id SERIAL PRIMARY KEY,
                         telegram_id BIGINT UNIQUE,
                         name TEXT,
                         total_buyin DOUBLE PRECISION DEFAULT 0.0,
                         total_cashout DOUBLE PRECISION DEFAULT 0.0,
                         registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         games_played INTEGER DEFAULT 0)''')

        c.execute('''CREATE TABLE IF NOT EXISTS games (
                     id SERIAL PRIMARY KEY,
                     date TIMESTAMP,
                     is_active BOOLEAN DEFAULT TRUE,
                     password TEXT,
                     creator_id BIGINT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                     id SERIAL PRIMARY KEY,
                     player_id INTEGER,
                     game_id INTEGER,
                     amount DOUBLE PRECISION,
                     type TEXT,
                     FOREIGN KEY(player_id) REFERENCES players(id),
                     FOREIGN KEY(game_id) REFERENCES games(id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS game_players (
                     id SERIAL PRIMARY KEY,
                     player_id INTEGER,
                     game_id INTEGER,
                     FOREIGN KEY(player_id) REFERENCES players(id),
                     FOREIGN KEY(game_id) REFERENCES games(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
                     id SERIAL PRIMARY KEY,
                     setting_name TEXT UNIQUE,
                     setting_value BOOLEAN)''')
        c.execute(
            "INSERT INTO settings (setting_name, setting_value) VALUES (%s, %s) ON CONFLICT (setting_name) DO NOTHING",
            ('allow_new_game', False))

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()


def get_db_connection():
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        # Parse DATABASE_URL
        result = urlparse(database_url)
        conn = psycopg2.connect(
            host=result.hostname,
            port=result.port,
            user=result.username,
            password=result.password,
            database=result.path[1:] if result.path else db_name,  # Remove leading '/' or use db_name
            sslmode="require"
        )
        conn.set_session(autocommit=True)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise



@bot.message_handler(commands=['menu'])
@safe_handler
def help_command(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('/new_game', '/join')
    keyboard.row('/rebuy', '/cashout')
    keyboard.row('/reset', '/end_game')
    keyboard.row('/game_results', '/menu')

    bot.send_message(message.chat.id, "🃏 Tap a command to execute:", reply_markup=keyboard)



@bot.message_handler(commands=['admin'])
@safe_handler
def show_admin_commands(message):
    admin_commands = """
Admin commands:
/check_db — List all registered players
/overall_results — Show overall results across all games
/avg_profit — Show average profit per game
/remove_player — Remove a player from the current game
/adjust — Adjust buy-in, rebuy, cashout, or clear for a player
/allow_new_game - Any player can create a new game
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
    c.execute("INSERT INTO players (telegram_id, name) VALUES (%s, %s) ON CONFLICT (telegram_id) DO NOTHING", (user_id, name))
    conn.commit()
    conn.close()
    bot.reply_to(message,
                 f"{name}, you are registered!\n\n"
                 f"Push /menu "
                 )


# New game
@bot.message_handler(commands=['new_game'])
@safe_handler
def new_game(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    c = conn.cursor()

    # Check if user is registered
    c.execute("SELECT id FROM players WHERE telegram_id = %s", (user_id,))
    if not c.fetchone():
        bot.reply_to(message, "❌ You are not registered. Use /start.")
        conn.close()
        return

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
    bot.register_next_step_handler(message, process_game_password)
    conn.close()

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
    conn.close()

def process_game_password(message):
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
        conn.close()
    except Exception as e:
        print("Error creating game:", e)
        bot.reply_to(message, "❌ Enter a valid 4-digit password. /new_game")

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
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id, password = game
    bot.reply_to(message, f"{name}, enter the 4-digit password for game #{game_id}:")
    bot.register_next_step_handler(message, lambda m: process_join_password(m, game_id, password, player_id, name))
    conn.close()


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
        bot.reply_to(message, f"{suits}{name}, enter buy-in amount (example: 20):")
        bot.register_next_step_handler(message, process_buyin)
        conn.close()
    except Exception as e:
        print("Error joining game:", e)
        bot.reply_to(message, "❌ Try to /join again.")


def process_buyin(message):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount_text = message.text.strip()
        amount = float(amount_text)
        if not (amount > 0 and round(amount, 1) == amount):
            raise ValueError("Amount must be a positive number with up to one decimal place (e.g., 20 or 20.5).")
        user_id = message.from_user.id
        name = message.from_user.first_name

        conn = get_db_connection()
        c = conn.cursor()

        # Get the ID of the currently active game
        c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            bot.reply_to(message, "❌ No active game found.")
            conn.close()
            return
        game_id = row[0]

        # Check if the player is registered
        c.execute("SELECT id FROM players WHERE telegram_id = %s", (user_id,))
        player = c.fetchone()
        if not player:
            bot.reply_to(message, "❌ You are not registered. Use /start.")
            conn.close()
            return
        player_id = player[0]

        # Check if already joined
        c.execute("SELECT id FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        if c.fetchone():
            bot.reply_to(message, f"{suits}{name}, you are already in game #{game_id}.")
            conn.close()
            return

        # Add player to game and increment games_played
        c.execute("INSERT INTO game_players (player_id, game_id) VALUES (%s, %s)", (player_id, game_id))
        c.execute("UPDATE players SET games_played = games_played + 1 WHERE id = %s", (player_id,))

        # Save the buy-in transaction (amount is negative)
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (%s, %s, %s, %s)",
                  (player_id, game_id, -amount, 'buyin'))

        # Update total buy-in
        c.execute("UPDATE players SET total_buyin = total_buyin + %s WHERE id = %s", (amount, player_id))

        conn.commit()
        bot.reply_to(message, f"✅ {name} has joined game #{game_id} with a buy-in of {amount:.1f}{suits}.")
    except Exception as e:
        print("Error in buy-in process:", e)
        bot.reply_to(message, "❌ Try to /join again. Example: 20 or 20.5")
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
        bot.reply_to(message, "You should join to the current game")
        conn.close()
        return

    bot.reply_to(message, "Enter the rebuy amount (example: 50)")
    bot.register_next_step_handler(message, process_rebuy)
    conn.close()

def process_rebuy(message):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount = float(message.text.strip())
        if not (amount > 0 and round(amount, 1) == amount):
            raise ValueError("Amount must be a positive number with up to one decimal place (e.g., 20 or 20.5).")
        user_id = message.from_user.id
        name = message.from_user.first_name

        conn = get_db_connection()
        c = conn.cursor()

        # Get active game
        c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            bot.reply_to(message, "❌ No active game found.")
            conn.close()
            return
        game_id = row[0]

        # Check player registration
        c.execute("SELECT id FROM players WHERE telegram_id = %s", (user_id,))
        player = c.fetchone()
        if not player:
            bot.reply_to(message, "❌ You are not registered. Use /start.")
            conn.close()
            return
        player_id = player[0]

        # Insert rebuy record
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (%s, %s, %s, %s)",
                  (player_id, game_id, -amount, 'rebuy'))

        # Update total buy-in
        c.execute("UPDATE players SET total_buyin = total_buyin + %s WHERE id = %s", (amount, player_id))

        conn.commit()
        bot.reply_to(message, f"✅ {name} made a rebuy of {amount:.1f}{suits} in game #{game_id}.")
    except Exception as e:
        print("Error in rebuy:", e)
        bot.reply_to(message, "❌ Try to /rebuy again. Example: 20 or 20.5")
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

    bot.reply_to(message, "Enter cashout amount (example: 11.4)")
    bot.register_next_step_handler(message, process_cashout)
    conn.close()

def process_cashout(message):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount = float(message.text.strip())
        if not (amount > 0 and round(amount, 1) == amount):
            raise ValueError("Amount must be a positive number with up to one decimal place (e.g., 20 or 20.5).")
        user_id = message.from_user.id
        name = message.from_user.first_name

        conn = get_db_connection()
        c = conn.cursor()

        # Find active game
        c.execute("SELECT id FROM games WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            bot.reply_to(message, "❌ No active game session.")
            conn.close()
            return
        game_id = row[0]

        # Get player ID
        c.execute("SELECT id FROM players WHERE telegram_id = %s", (user_id,))
        player = c.fetchone()
        if not player:
            bot.reply_to(message, "❌ You are not registered. Use /start.")
            conn.close()
            return
        player_id = player[0]

        # Save cashout
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (%s, %s, %s, %s)",
                  (player_id, game_id, amount, 'cashout'))

        # Update total cashout
        c.execute("UPDATE players SET total_cashout = total_cashout + %s WHERE id = %s", (amount, player_id))

        conn.commit()
        bot.reply_to(message, f"✅ {name} cashed out {amount:.1f}{suits} in game #{game_id}.")
    except Exception as e:
        print("Cashout error:", e)
        bot.reply_to(message, "❌ Try to /cashout again. Example: 20 or 20.5")
    finally:
        if 'conn' in locals():
            conn.close()

@bot.message_handler(commands=['reset'])
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
    bot.reply_to(message, f"{name}, enter the 4-digit password for game #{game_id}:")
    bot.register_next_step_handler(message, lambda m: process_reset_password(m, game_id, password, player_id, name))
    conn.close()

def process_reset_password(message, game_id, correct_password, player_id, name):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        password = message.text.strip()
        if password != correct_password:
            bot.reply_to(message, "❌ Incorrect password. Try /reset again.")
            return
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT amount, type FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        transactions = c.fetchall()
        for amount, trans_type in transactions:
            if trans_type in ['buyin', 'rebuy']:
                c.execute("UPDATE players SET total_buyin = total_buyin - %s WHERE id = %s", (-amount, player_id))
            elif trans_type == 'cashout':
                c.execute("UPDATE players SET total_cashout = total_cashout - %s WHERE id = %s", (amount, player_id))
        c.execute("DELETE FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        c.execute("DELETE FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        c.execute("UPDATE players SET games_played = games_played - 1 WHERE id = %s", (player_id,))
        conn.commit()
        bot.reply_to(message, f"✅ {name}'s transactions and participation in game #{game_id} have been reset{suits}.")
    except Exception as e:
        print("Error in reset:", e)
        bot.reply_to(message, "❌ Error resetting. Try /reset again.")
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
        bot.reply_to(message, "⚠️ No active game. Enter the game ID to view past results:")
        bot.register_next_step_handler(message, process_game_results)

def process_game_results(message):
    try:
        game_id = int(message.text.strip())
        send_game_results_to_user(game_id, message.chat.id)
    except Exception as e:
        print("Game results error:", e)
        bot.reply_to(message, "❌ Try to see /game_results again with correct game ID.")

def send_game_results_to_user(game_id, chat_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.name, 
               SUM(CASE WHEN t.type = 'buyin' THEN -t.amount ELSE 0 END) as buyins,
               SUM(CASE WHEN t.type = 'rebuy' THEN -t.amount ELSE 0 END) as rebuys,
               SUM(CASE WHEN t.type = 'cashout' THEN t.amount ELSE 0 END) as cashouts,
               SUM(t.amount) as total
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

    for name, buyins, rebuys, cashouts, total in results:
        total_buyins += buyins
        total_rebuys += rebuys
        total_cashouts += cashouts
        response += (
            f"{name}: Buy-in: {buyins}, Rebuy: {rebuys}, "
            f"Cashout: {cashouts}, Total: {'+' if total > 0 else ''}{total}\n"
        )

    total_in = total_buyins + total_rebuys
    total_out = total_cashouts
    diff = total_in - total_out

    response += (
        f"\n💰 Game total:\n"
        f"  Buy-ins + Rebuys = {total_in}\n"
        f"  Cashouts = {total_out}\n"
        f"  Difference = {round(diff, 1) if diff != 0 else '✅ OK — balanced'}"
    )

    bot.send_message(chat_id, response)


# Overall results
@bot.message_handler(commands=['overall_results'])
@safe_handler
def overall_results(message):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
                SELECT p.name, 
                       p.games_played, 
                       (p.total_cashout - p.total_buyin) as total_profit,
                       SUM(CASE WHEN s.total > 0 THEN 1 ELSE 0 END) as positive_games,
                       COUNT(DISTINCT s.game_id) as total_games
                FROM players p
                LEFT JOIN (
                    SELECT player_id, game_id, SUM(amount) as total
                    FROM transactions
                    GROUP BY player_id, game_id
                ) s ON s.player_id = p.id
                GROUP BY p.id
            """)
    results = c.fetchall()
    conn.close()

    if not results:
        bot.reply_to(message, "No player data found.")
        return

    # Create table header
    response = "📊 Overall Results:\n"
    response += f"{'Name':<15} | {'Games':<8} | {'Total $':<10} | {'Profitable Games':<18}\n"
    response += "-" * 55 + "\n"

    # Fill table rows
    for name, games_played, total_profit, positive_games, total_games in results:
        total_profit = total_profit or 0  # Handle NULL for players with no transactions
        total_games = total_games or 0
        positive_games = positive_games or 0
        profitable_percent = (positive_games / total_games * 100) if total_games > 0 else 0
        # Truncate name to 15 characters
        name = name[:15]
        # Format total_profit to ensure consistent width
        profit_str = f"{'+' if total_profit > 0 else ''}{total_profit}"
        response += f"{name:<15} | {games_played:<8} | {profit_str:<10} | {profitable_percent:>5.1f}% ({positive_games}/{total_games})\n"

    bot.reply_to(message, response)


# average profit per game
@bot.message_handler(commands=['avg_profit'])
@safe_handler
def avg_profit(message):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.name, AVG(s.total)
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
        response += f"{name}: {'+' if avg > 0 else ''}{avg:.2f}\n"
    bot.reply_to(message, response)


#ADMINS
@bot.message_handler(commands=['check_db'])
@safe_handler
def check_db(message):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "Access denied!")
        return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM players")
    players = c.fetchall()
    conn.close()

    if not players:
        bot.reply_to(message, "No players found in the database.")
        return

    response = "Players:\n"
    for player in players:
        player_id, telegram_id, name, total_buyin, total_cashout, registered_at, games_played = player
        response += (
            f"🆔 ID: {player_id}\n"
            f"👤 Name: {name}\n"
            f"📱 Telegram ID: {telegram_id}\n"
            f"💰 Total profit: {total_cashout - total_buyin}\n"
            f"{suits}Games played: {games_played}\n"
            f"Registered: {registered_at}\n"
            "-----------------------\n"
        )
    bot.reply_to(message, response)


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
    c.execute("SELECT p.id, p.name FROM players p JOIN game_players gp ON p.id = gp.player_id WHERE gp.game_id = %s", (game_id,))
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
            if trans_type in ['buyin', 'rebuy']:
                c.execute("UPDATE players SET total_buyin = total_buyin - %s WHERE id = %s", (-amount, player_id))
            elif trans_type == 'cashout':
                c.execute("UPDATE players SET total_cashout = total_cashout - %s WHERE id = %s", (amount, player_id))
        c.execute("DELETE FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        c.execute("DELETE FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
        c.execute("UPDATE players SET games_played = games_played - 1 WHERE id = %s", (player_id,))
        conn.commit()
        bot.answer_callback_query(call.id, f"{name} removed from game #{game_id}{suits}.")
        bot.edit_message_text(f"✅ {name} removed from game #{game_id}{suits}.", call.message.chat.id, call.message.message_id)
    except Exception as e:
        print("Error in remove_player callback:", e)
        bot.answer_callback_query(call.id, "Error removing player.")
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
    c.execute("SELECT p.id, p.name FROM players p JOIN game_players gp ON p.id = gp.player_id WHERE gp.game_id = %s", (game_id,))
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
        bot.edit_message_text(f"Adjust for {name} in game #{game_id}:", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except Exception as e:
        print("Error in adjust player callback:", e)
        bot.answer_callback_query(call.id, "Error selecting player.")
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
            c.execute("SELECT amount, type FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
            transactions = c.fetchall()
            for amount, trans_type in transactions:
                if trans_type in ['buyin', 'rebuy']:
                    c.execute("UPDATE players SET total_buyin = total_buyin - %s WHERE id = %s", (-amount, player_id))
                elif trans_type == 'cashout':
                    c.execute("UPDATE players SET total_cashout = total_cashout - %s WHERE id = %s", (amount, player_id))
            c.execute("DELETE FROM transactions WHERE player_id = %s AND game_id = %s", (player_id, game_id))
            c.execute("DELETE FROM game_players WHERE player_id = %s AND game_id = %s", (player_id, game_id))
            c.execute("UPDATE players SET games_played = games_played - 1 WHERE id = %s", (player_id,))
            conn.commit()
            bot.answer_callback_query(call.id, f"{name}'s transactions cleared in game #{game_id}{suits}.")
            bot.edit_message_text(f"✅ {name}'s transactions and participation in game #{game_id} cleared{suits}.", call.message.chat.id, call.message.message_id)
        else:
            action_type = 'rebuy' if action == 'rebuy' else 'cashout'
            bot.edit_message_text(f"Enter {action_type} amount for {name} in game #{game_id} (example: 20 or 20.5):", call.message.chat.id, call.message.message_id)
            bot.register_next_step_handler_by_chat_id(call.message.chat.id, lambda m: process_adjust_amount(m, game_id, player_id, action_type, name))
    except Exception as e:
        print(f"Error in {action} callback:", e)
        bot.answer_callback_query(call.id, f"Error processing {action}.")
    finally:
        if 'conn' in locals():
            conn.close()

# Add function to process rebuy or cashout amount
def process_adjust_amount(message, game_id, player_id, action_type, name):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount = float(message.text.strip())
        if not (amount > 0 and round(amount, 1) == amount):
            raise ValueError("Amount must be a positive number with up to one decimal place (e.g., 20 or 20.5).")
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
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (%s, %s, %s, %s)",
                  (player_id, game_id, amount_value, action_type))
        if action_type == 'rebuy':
            c.execute("UPDATE players SET total_buyin = total_buyin + %s WHERE id = %s", (amount, player_id))
        else:
            c.execute("UPDATE players SET total_cashout = total_cashout + %s WHERE id = %s", (amount, player_id))
        conn.commit()
        bot.reply_to(message, f"✅ {name} {action_type} of {amount:.1f}{suits} in game #{game_id}.")
    except Exception as e:
        print(f"Error in {action_type} amount processing:", e)
        bot.reply_to(message, f"❌ Try again. Example: 20 or 20.5")
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


# Start bot
if __name__ == '__main__':
    init_db()
    if not os.getenv("RAILWAY_ENVIRONMENT"):
        bot.remove_webhook()
        bot.polling()

