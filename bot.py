import telebot
from telebot import types
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Настройка бота
TOKEN = "7695681893:AAGt9Tf-Ov1NIfwVKn1DwDgPcRuxHbK01eA"
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


# Инициализация базы данных SQLite
def init_db():
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 telegram_id INTEGER UNIQUE,
                 name TEXT)''')
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
    conn.commit()
    conn.close()

@bot.message_handler(commands=['help'])
def help_command(message):
    commands = """
Доступные команды:
/start — Регистрация игрока
/new_game — Начать новую покерную сессию
/buyin — Добавить бай-ин (пример: 100 1)
/rebuy — Добавить докупку (пример: 50 1)
/cashout — Добавить кэшаут (пример: 150 1)
/game_results — Итоги сессии по ID
/overall_results — Общие результаты по всем играм
/avg_profit — Средний профит за сессию
/help — Показать список всех команд
"""
    bot.reply_to(message, commands)

# Регистрация игрока
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO players (telegram_id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"Hey {name}! Welcome to the game. Check out pinned message.")



# Новая игровая сессия
# Список ID пользователей, которым разрешено создавать игры
ADMINS = [300526718, ]  # ← замени на настоящие ID

@bot.message_handler(commands=['new_game'])
def new_game(message):
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "Wait for admin please")
        return

    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute("SELECT id FROM games WHERE is_active = 1")
    active = c.fetchone()
    if active:
        bot.reply_to(message, f"Сессия #{active[0]} уже активна. Завершите её командой /end_game.")
    else:
        c.execute("INSERT INTO games (date, is_active) VALUES (?, 1)", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        game_id = c.lastrowid
        conn.commit()
        bot.reply_to(message, f"Сессия #{game_id} создана!")
    conn.close()


# Конец игры
@bot.message_handler(commands=['end_game'])
def end_game(message):
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute("UPDATE games SET is_active = 0 WHERE is_active = 1")
    if c.rowcount > 0:
        bot.reply_to(message, "Текущая сессия завершена.")
    else:
        bot.reply_to(message, "Нет активной сессии.")
    conn.commit()
    conn.close()


# Добавление бай-ина
@bot.message_handler(commands=['buyin'])
def buyin(message):
    bot.reply_to(message, "Введите сумму бай-ина и (необязательно) ID сессии. Примеры:\n100\n100 2")
    bot.register_next_step_handler(message, process_buyin)

def process_buyin(message):
    try:
        parts = message.text.strip().split()
        if not parts or not parts[0].isdigit():
            raise ValueError("Некорректная сумма")

        amount = int(parts[0])
        user_id = message.from_user.id
        name = message.from_user.first_name

        conn = sqlite3.connect('poker.db')
        c = conn.cursor()

        # Получаем ID сессии
        if len(parts) == 2:
            game_id = int(parts[1])
            c.execute("SELECT id FROM games WHERE id = ? AND is_active = 1", (game_id,))
        else:
            c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")

        row = c.fetchone()
        if not row:
            bot.reply_to(message, "❌ Активная сессия не найдена или ID указан неверно.")
            return

        game_id = row[0]

        # Получаем ID игрока
        c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
        player = c.fetchone()
        if not player:
            bot.reply_to(message, "❌ Вы не зарегистрированы. Используйте /start.")
            return

        player_id = player[0]

        # Сохраняем бай-ин
        c.execute("""
            INSERT INTO transactions (player_id, game_id, amount, type)
            VALUES (?, ?, ?, ?)""", (player_id, game_id, -amount, 'buyin'))
        conn.commit()
        bot.reply_to(message, f"✅ {name} внёс бай-ин {amount} в сессию #{game_id}.")
    except Exception as e:
        print("Ошибка в бай-ине:", e)
        bot.reply_to(message, "❌ Ошибка! Формат: сумма или сумма ID_сессии (пример: 100 или 100 2)")
    finally:
        if 'conn' in locals():
            conn.close()



# Добавление докупки
@bot.message_handler(commands=['rebuy'])
def rebuy(message):
    bot.reply_to(message, "Введите сумму докупки (пример: 50)")
    bot.register_next_step_handler(message, process_rebuy)

def process_rebuy(message):
    try:
        amount = int(message.text.strip())
        user_id = message.from_user.id
        name = message.from_user.first_name

        conn = sqlite3.connect('poker.db')
        c = conn.cursor()

        # Получаем активную сессию
        c.execute("SELECT id FROM games WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            bot.reply_to(message, "❌ Нет активной сессии.")
            return

        game_id = row[0]

        # Проверка регистрации игрока
        c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
        player = c.fetchone()
        if not player:
            bot.reply_to(message, "❌ Вы не зарегистрированы. Используйте /start.")
            return

        player_id = player[0]

        # Вставляем запись о докупке
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (?, ?, ?, ?)",
                  (player_id, game_id, -amount, 'rebuy'))
        conn.commit()
        bot.reply_to(message, f"✅ {name} сделал докупку {amount} в сессию #{game_id}.")
    except Exception as e:
        print("Ошибка в докупке:", e)
        bot.reply_to(message, "❌ Ошибка! Введите только сумму (например: 50)")
    finally:
        if 'conn' in locals():
            conn.close()




# Добавление кэшаута
@bot.message_handler(commands=['cashout'])
def cashout(message):
    bot.reply_to(message, "Введите сумму кэшаута и ID сессии (пример: 150 1)")
    bot.register_next_step_handler(message, process_cashout)

def process_cashout(message):
    try:
        amount, game_id = map(int, message.text.split())
        user_id = message.from_user.id
        conn = sqlite3.connect('poker.db')
        c = conn.cursor()
        c.execute("SELECT id FROM players WHERE telegram_id = ?", (user_id,))
        player_id = c.fetchone()[0]
        c.execute("INSERT INTO transactions (player_id, game_id, amount, type) VALUES (?, ?, ?, ?)",
                  (player_id, game_id, amount, 'cashout'))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"Кэшаут {amount} для сессии #{game_id} записан.")
    except:
        bot.reply_to(message, "Ошибка! Введите: сумма ID_сессии (пример: 150 1)")



# Итоги сессии
@bot.message_handler(commands=['game_results'])
def game_results(message):
    bot.reply_to(message, "Введите ID сессии для итогов")
    bot.register_next_step_handler(message, process_game_results)

def process_game_results(message):
    try:
        game_id = int(message.text)
        conn = sqlite3.connect('poker.db')
        c = conn.cursor()
        c.execute("""
            SELECT p.name, SUM(t.amount)
            FROM transactions t
            JOIN players p ON t.player_id = p.id
            WHERE t.game_id = ?
            GROUP BY p.id
        """, (game_id,))
        results = c.fetchall()
        conn.close()
        response = f"Итоги сессии #{game_id}:\n"
        for name, total in results:
            response += f"{name}: {'+' if total > 0 else ''}{total}\n"
        bot.reply_to(message, response)
    except:
        bot.reply_to(message, "Ошибка! Введите ID сессии (пример: 1)")

def send_game_results_to_group(game_id, chat_id):
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute("""
        SELECT p.name, SUM(t.amount)
        FROM transactions t
        JOIN players p ON t.player_id = p.id
        WHERE t.game_id = ?
        GROUP BY p.id
    """, (game_id,))
    results = c.fetchall()
    conn.close()
    response = f"Итоги сессии #{game_id}:\n"
    for name, total in results:
        response += f"{name}: {'+' if total > 0 else ''}{total}\n"
    bot.send_message(chat_id, response)



# Общие итоги
@bot.message_handler(commands=['overall_results'])
def overall_results(message):
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    # Общий плюс/минус
    c.execute("""
        SELECT p.name, SUM(t.amount) as total
        FROM transactions t
        JOIN players p ON t.player_id = p.id
        GROUP BY p.id
    """)
    totals = c.fetchall()
    # Процент плюсовых сессий
    c.execute("""
        SELECT p.name, 
               SUM(CASE WHEN s.total > 0 THEN 1 ELSE 0 END) as positive_games,
               COUNT(DISTINCT t.game_id) as total_games
        FROM transactions t
        JOIN players p ON t.player_id = p.id
        JOIN (
            SELECT game_id, SUM(amount) as total
            FROM transactions
            GROUP BY game_id
        ) s ON t.game_id = s.game_id
        GROUP BY p.id
    """)
    games = c.fetchall()
    conn.close()
    response = "Общие итоги:\n"
    for name, total in totals:
        response += f"{name}: {'+' if total > 0 else ''}{total}\n"
    response += "\nПроцент плюсовых сессий:\n"
    for name, pos, total_s in games:
        percent = (pos / total_s * 100) if total_s > 0 else 0
        response += f"{name}: {percent:.1f}% ({pos}/{total_s})\n"
    bot.reply_to(message, response)



# Полезная статистика: средний профит за сессию
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
    response = "Средний профит за сессию:\n"
    for name, avg in results:
        response += f"{name}: {'+' if avg > 0 else ''}{avg:.2f}\n"
    bot.reply_to(message, response)



ADMIN_ID = 300526718  # Вставь свой Telegram ID
@bot.message_handler(commands=['check_db'])
def check_db(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "Доступ запрещён!")
        return
    conn = sqlite3.connect('poker.db')
    c = conn.cursor()
    c.execute("SELECT * FROM players")
    players = c.fetchall()
    conn.close()
    bot.reply_to(message, f"Игроки: {players}")
# Запуск бота
if __name__ == '__main__':
    init_db()
    bot.polling()

# 3. Создай файл requirements.txt:
# pyTelegramBotAPI==4.14.0
# SQLAlchemy==2.0.23

# 4. Для работы на Replit:
# - Создай проект на Replit, загрузи bot.py и requirements.txt.
# - Вставь токен в код.
# - Запусти проект (Replit установит зависимости и запустит бота).

# 5. Для работы 24/7:
# - В Replit включи "Always On" (в бесплатной версии ограничено).
# - Или используй PythonAnywhere: загрузи файлы, настрой запуск bot.py.