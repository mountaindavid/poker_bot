# 🃏 PokerBot - Telegram Bot для покерных игр

Telegram бот для управления покерными играми с отслеживанием buy-ins, rebuys и cashouts.

## ✨ Возможности

- 🎮 Создание и управление играми
- 💰 Отслеживание buy-ins, rebuys, cashouts
- 📊 Статистика по играм и игрокам
- 🔐 Защита паролем для игр
- 👥 Административные функции
- 📈 Win rate и средний профит

## 🚀 Быстрый старт

### Предварительные требования
- Python 3.8+
- PostgreSQL
- Telegram Bot Token

### Установка

1. **Клонируйте репозиторий**
```bash
git clone <repository-url>
cd holdem_poker_bot
```

2. **Настройте виртуальное окружение**
```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# или
.venv\Scripts\activate     # Windows
```

3. **Установите зависимости**
```bash
pip install -r requirements.txt
```

4. **Настройте базу данных**
```bash
# Создайте пользователя и базу
sudo -u postgres psql
CREATE USER pokerbot WITH PASSWORD 'your_password';
CREATE DATABASE pokerbot_dev OWNER pokerbot;
GRANT ALL PRIVILEGES ON DATABASE pokerbot_dev TO pokerbot;
\q
```

5. **Создайте .env файл**
```bash
cp env.example .env
# Отредактируйте .env с вашими настройками
```

6. **Запустите бота**
```bash
# Локальный режим (для разработки)
python run_local.py

# Webhook режим (для продакшена)
python main.py
```

## 📋 Команды бота

### Основные команды
- `/start` - Регистрация
- `/menu` - Главное меню
- `/new_game` - Создать новую игру
- `/join` - Присоединиться к игре
- `/rebuy` - Добавить фишки
- `/cashout` - Вывести деньги
- `/leave` - Покинуть игру
- `/game_results` - Результаты игры
- `/overall_results` - Общая статистика

### Административные команды
- `/remove_player` - Удалить игрока
- `/adjust` - Корректировка транзакций
- `/allow_new_game` - Разрешить создание игр
- `/notifications_switcher` - Управление уведомлениями

## 🏗️ Архитектура

### Структура проекта
```
holdem_poker_bot/
├── bot.py              # Основной файл бота
├── main.py             # Webhook сервер
├── run_local.py        # Локальный запуск
├── migrations.py       # Система миграций БД
├── requirements.txt    # Зависимости
├── Procfile           # Конфигурация Railway
└── .env               # Переменные окружения
```

### База данных
- **players** - Игроки и их статистика
- **games** - Игры и их статус
- **transactions** - Все транзакции (buyin/rebuy/cashout)
- **game_players** - Связь игроков с играми
- **settings** - Настройки бота

## 🚀 Деплой

### Railway (рекомендуется)
1. Подключите репозиторий к Railway
2. Настройте переменные окружения:
   - `TELEGRAM_BOT_TOKEN`
   - `DATABASE_URL`
   - `WEBHOOK_URL`
   - `WEBHOOK_SECRET_PATH`
3. Деплой произойдет автоматически

### Heroku
1. Создайте приложение в Heroku
2. Подключите PostgreSQL addon
3. Настройте переменные окружения
4. Деплойте через Git

## 🔧 Разработка

### Локальная разработка
```bash
# Активируйте окружение
source .venv/bin/activate

# Запустите в режиме разработки
python run_local.py

# Для тестирования webhook
python main.py
```

### Миграции базы данных
```bash
# Применить все миграции
python migrations.py

# Откатить миграцию
python migrations.py rollback <migration_name>
```

### Структура кода
- **bot.py** - Монолитный файл (1441 строка) - требует рефакторинга
- **migrations.py** - Система миграций БД
- **main.py** - Flask webhook сервер
- **run_local.py** - Локальный запуск в polling режиме

## 📊 Статистика

### Текущее состояние
- ✅ Функциональный Telegram бот
- ✅ PostgreSQL база данных
- ✅ Система миграций
- ✅ Деплой на Railway
- ⚠️ Монолитный код (1441 строка)
- ⚠️ Отсутствие тестов
- ⚠️ Нет CI/CD

### Планы развития
1. **Модуляризация** - Разбить bot.py на модули
2. **Тестирование** - Добавить unit и integration тесты
3. **CI/CD** - Настроить автоматические проверки
4. **Документация** - Улучшить API документацию

## 🐛 Устранение неполадок

### Частые проблемы
1. **Ошибка подключения к БД** - Проверьте настройки PostgreSQL
2. **Не работает webhook** - Проверьте WEBHOOK_URL и токен
3. **Ошибки в расчетах** - Проверьте миграции БД

### Логи
```bash
# Просмотр логов в Railway
railway logs

# Локальные логи
tail -f bot.log
```

## 📞 Поддержка

- Создайте issue в репозитории
- Проверьте логи для диагностики
- Убедитесь, что все переменные окружения настроены

## 📄 Лицензия

MIT License 


PGPASSWORD="cYkKaLpSYNEfTwogLZDicHPjdehxpetg" pg_dump \
  -h crossover.proxy.rlwy.net \
  -p 14418 \
  -U postgres \
  -d railway \
  -F p \
  -f railway_dump.sql