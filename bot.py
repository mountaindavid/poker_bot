import telebot, os, random
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Bot setup
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     telegram_id INTEGER UNIQUE,
                     name TEXT,
                     total_buyin INTEGER DEFAULT 0,
                     total_cashout INTEGER DEFAULT 0,
                     registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                     games_played INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS games (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 date TEXT,
                 is_active INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 player_id INTEGER,
                 game_id INTEGER,
                 amount REAL,
                 type TEXT,
                 FOREIGN KEY(player_id) REFERENCES players(id),
                 FOREIGN KEY(game_id) REFERENCES games(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS game_players (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 player_id INTEGER,
                 game_id INTEGER,
                 FOREIGN KEY(player_id) REFERENCES players(id),
                 FOREIGN KEY(game_id) REFERENCES games(id))''')
    conn.commit()
    conn.close()


@bot.message_handler(commands=['help'])
def help_command(message):
    commands = """
🃏Basic commands:
/start — Register as a player
/new_game — New poker game (admins only)

/join — Join the current game
/rebuy — Add a rebuy
/cashout — Add a cashout

/end_game — End the current game (admins only)
/game_results — Show results for a game by ID
/help — Show this help message
"""
    bot.reply_to(message, commands)


@bot.message_handler(commands=['admin'])
def show_admin_commands(message):
    admin_commands = """
Admin commands:
/check_db — Admin command: list all registered players
/overall_results — Show overall results across all games
/avg_profit — Show average profit per game
    """
    bot.reply_to(message, admin_commands)


# Player registration
@bot.message_handler(commands=['start'])
def register(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO players (telegram_id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()
    bot.reply_to(message,
                 f"{name}, you are registered!\n\n"
                 f"🃏 Basic commands:\n"
                 f"/start — Register as a player\n"
                 f"/new_game — Start a new poker game\n"
                 f"/join — Join the current game\n"
                 f"/rebuy — Add a rebuy\n"
                 f"/cashout — Add a cashout\n"
                 f"/end_game — End the current game\n"
                 f"/game_results — Game results\n"
                 f"/help — Show this help message"
                 )


# List of user IDs allowed to create games
ADMINS = [300526718, ]
# New game
@bot.message_handler(commands=['new_game'])
def new_game(message):
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "Please wait for an admin.")
        return
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute("SELECT id FROM games WHERE is_active = 1")
    active = c.fetchone()
    if active:
        bot.reply_to(message, f"Game #{active[0]} is already active. End it first with /end_game.")
    else:
        c.execute("INSERT INTO games (date, is_active) VALUES (?, 1)", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        game_id = c.lastrowid
        conn.commit()
        bot.reply_to(message, f"Game #{game_id} created!")
    conn.close()


# End game
@bot.message_handler(commands=['end_game'])
def end_game(message):
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "Please wait for an admin.")
        return
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    # Get active game ID
    c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id = game[0]
    # End the game
    c.execute("UPDATE games SET is_active = 0 WHERE is_active = 1")
    conn.commit()
    bot.reply_to(message, f"Game #{game_id} ended.")
    conn.close()


@bot.message_handler(commands=['join'])
def join_game(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = sqlite3.connect('poker.db')
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    c = conn.cursor()
    # Check if player is registered
    c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
    player = c.fetchone()
    if not player:
        bot.reply_to(message, "❌ You are not registered. Use /start.")
        conn.close()
        return
    player_id = player[0]
    # Check active game
    c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id = game[0]
    # Check if already joined
    c.execute("SELECT id FROM game_players WHERE player_id = ? AND game_id = ?", (player_id, game_id))
    if c.fetchone():
        bot.reply_to(message, f"{suits}{name}, you are already in game #{game_id}.")
        conn.close()
        return
    # Request buy-in amount
    bot.reply_to(message, f"{name}, enter buy-in amount (example: 20):")
    bot.register_next_step_handler(message, process_buyin)
    conn.close()

def process_buyin(message):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    try:
        amount_text = message.text.strip()
        if not amount_text.isdigit():
            raise ValueError("Only numbers are allowed.")
        amount = int(amount_text)
        user_id = message.from_user.id
        name = message.from_user.first_name

        conn = sqlite3.connect('poker.db')
        c = conn.cursor()

        # Get the ID of the currently active game
        c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            bot.reply_to(message, "❌ No active game found.")
            conn.close()
            return
        game_id = row[0]

        # Check if the player is registered
        c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
        player = c.fetchone()
        if not player:
            bot.reply_to(message, "❌ You are not registered. Use /start.")
            conn.close()
            return
        player_id = player[0]

        # Check if already joined (to prevent race conditions)
        c.execute("SELECT id FROM game_players WHERE player_id = ? AND game_id = ?", (player_id, game_id))
        if c.fetchone():
            bot.reply_to(message, f"{suits}{name}, you are already in game #{game_id}.")
            conn.close()
            return

        # Add player to game and increment games_played
        c.execute("INSERT INTO game_players (player_id, game_id) VALUES (?, ?)", (player_id, game_id))
        c.execute("UPDATE players SET games_played = games_played + 1 WHERE id = ?", (player_id,))

        # Save the buy-in transaction (amount is negative)
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (?, ?, ?, ?)",
                  (player_id, game_id, -amount, 'buyin'))

        # Update total buy-in
        c.execute("UPDATE players SET total_buyin = total_buyin + ? WHERE id = ?", (amount, player_id))

        conn.commit()
        bot.reply_to(message, f"✅ {name} has joined game #{game_id} with a buy-in of {amount}{suits}.")
    except Exception as e:
        print("Error in buy-in process:", e)
        bot.reply_to(message, "❌Try to /join again. Example: 20")
    finally:
        if 'conn' in locals():
            conn.close()


# Add rebuy
@bot.message_handler(commands=['rebuy'])
def rebuy(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()

    # Check active game
    c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game found.")
        conn.close()
        return
    game_id = game[0]

    # Check if player is registered
    c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
    player = c.fetchone()
    if not player:
        bot.reply_to(message, "❌ You are not registered. Use /register.")
        conn.close()
        return
    player_id = player[0]

    # Check if player joined the active game
    c.execute("SELECT id FROM game_players WHERE player_id = ? AND game_id = ?", (player_id, game_id))
    if not c.fetchone():
        bot.reply_to(message, "You should join to the current game")
        conn.close()
        return

    bot.reply_to(message, "Enter the rebuy amount (example: 50)")
    bot.register_next_step_handler(message, process_rebuy)
    conn.close()

def process_rebuy(message):
    try:
        amount = int(message.text.strip())
        user_id = message.from_user.id
        name = message.from_user.first_name

        conn = sqlite3.connect('poker.db')
        c = conn.cursor()

        # Get active game
        c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            bot.reply_to(message, "❌ No active game found.")
            return

        game_id = row[0]

        # Check player registration
        c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
        player = c.fetchone()
        if not player:
            bot.reply_to(message, "❌ You are not registered. Use /start.")
            return

        player_id = player[0]

        # Insert rebuy record
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (?, ?, ?, ?)",
                  (player_id, game_id, -amount, 'rebuy'))

        #update total rebuy
        c.execute("UPDATE players SET total_buyin = total_buyin + ? WHERE id = ?", (amount, player_id))

        conn.commit()
        bot.reply_to(message, f"✅ {name} made a rebuy of {amount} in game #{game_id}.")
    except Exception as e:
        print("Error in rebuy:", e)
        bot.reply_to(message, "❌ Try to /rebuy again. Example: 20")
    finally:
        if 'conn' in locals():
            conn.close()


# Add cashout
@bot.message_handler(commands=['cashout'])
def cashout(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()

    # Check active game
    c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    game = c.fetchone()
    if not game:
        bot.reply_to(message, "❌ No active game session.")
        conn.close()
        return
    game_id = game[0]

    # Check if player is registered
    c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
    player = c.fetchone()
    if not player:
        bot.reply_to(message, "❌ You are not registered. Use /start.")
        conn.close()
        return
    player_id = player[0]

    # Check if player joined the active game
    c.execute("SELECT id FROM game_players WHERE player_id = ? AND game_id = ?", (player_id, game_id))
    if not c.fetchone():
        bot.reply_to(message, "You should join to the current game")
        conn.close()
        return

    bot.reply_to(message, "Enter cashout amount (example: 11.4)")
    bot.register_next_step_handler(message, process_cashout)
    conn.close()

def process_cashout(message):
    try:
        amount = int(message.text.strip())
        user_id = message.from_user.id
        name = message.from_user.first_name

        conn = sqlite3.connect('poker.db')
        c = conn.cursor()

        # Find active game
        c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            bot.reply_to(message, "❌ No active game session.")
            return
        game_id = row[0]

        # Get player ID
        c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
        player = c.fetchone()
        if not player:
            bot.reply_to(message, "❌ You are not registered. Use /start.")
            return
        player_id = player[0]

        # Save cashout
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (?, ?, ?, ?)",
                  (player_id, game_id, amount, 'cashout'))

        # update cashout
        c.execute("UPDATE players SET total_cashout = total_cashout + ? WHERE id = ?", (amount, player_id))

        conn.commit()
        bot.reply_to(message, f"✅ {name} cashed out {amount} in game #{game_id}.")
    except Exception as e:
        print("Cashout error:", e)
        bot.reply_to(message, "❌ Try to /cashout again. Example: 20")
    finally:
        if 'conn' in locals():
            conn.close()


# game results
@bot.message_handler(commands=['game_results'])
def game_results(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()

    # search active game
    c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
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
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute("""
        SELECT p.name, 
               SUM(CASE WHEN t.type = 'buyin' THEN -t.amount ELSE 0 END) as buyins,
               SUM(CASE WHEN t.type = 'rebuy' THEN -t.amount ELSE 0 END) as rebuys,
               SUM(CASE WHEN t.type = 'cashout' THEN t.amount ELSE 0 END) as cashouts,
               SUM(t.amount) as total
        FROM transactions t
        JOIN players p ON t.player_id = p.id
        WHERE t.game_id = ?
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
        f"  Difference = {diff if diff != 0 else '✅ OK — balanced'}"
    )

    bot.send_message(chat_id, response)


# Overall results
@bot.message_handler(commands=['overall_results'])
def overall_results(message):
    conn = sqlite3.connect('poker.db')
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
    response += "Name        | Games | Total $ | Profitable Games (%)\n"
    response += "-" * 50 + "\n"

    # Fill table rows
    for name, games_played, total_profit, positive_games, total_games in results:
        total_profit = total_profit or 0  # Handle NULL for players with no transactions
        total_games = total_games or 0
        positive_games = positive_games or 0
        profitable_percent = (positive_games / total_games * 100) if total_games > 0 else 0
        response += f"{name:<15} | {games_played:<12} | {'+' if total_profit > 0 else ''}{total_profit:<12} | {profitable_percent:.1f}% ({positive_games}/{total_games})\n"

    bot.reply_to(message, response)


# average profit per game
@bot.message_handler(commands=['avg_profit'])
def avg_profit(message):
    conn = sqlite3.connect('poker.db')
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
def check_db(message):
    suits = random.choice(['♠️', '♣️', '♥️', '♦️'])
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "Access denied!")
        return
    conn = sqlite3.connect('poker.db')
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


# Start bot
if __name__ == '__main__':
    init_db()
    bot.polling()

