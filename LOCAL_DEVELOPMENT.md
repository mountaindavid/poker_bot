# 🏠 Локальная разработка PokerBot

## 📋 Быстрый старт (если проект уже на Railway)

### Вариант 1: Использование локальной базы данных (рекомендуется)

#### 1. Настройка локальной PostgreSQL
```bash
# Запустите PostgreSQL (если не запущен)
brew services start postgresql@16

# Создайте базу данных
createdb pokerbot_dev
```

#### 2. Создайте файл .env для локальной разработки
```bash
cp env.example .env
```

Отредактируйте `.env`:
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Local Database Configuration
PGHOST=localhost
PGPORT=5432
PGUSER=david
PGPASSWORD=
PGDATABASE=pokerbot_dev

# Local Development (no webhook)
PORT=5000
```

#### 3. Запуск в режиме polling
```bash
# Активируйте виртуальное окружение
source .venv/bin/activate

# Запустите бота локально
python run_local.py
```

### Вариант 2: Использование Railway базы данных

#### 1. Получите данные подключения к Railway
```bash
# В Railway Dashboard -> Variables -> DATABASE_URL
# Скопируйте значение DATABASE_URL
```

#### 2. Создайте .env файл
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Railway Database
DATABASE_URL=postgresql://username:password@host:port/database

# Local Development
PORT=5000
```

#### 3. Запуск
```bash
source .venv/bin/activate
python run_local.py
```

## 🔧 Полезные команды

### Проверка подключения к базе данных
```bash
# Для локальной БД
psql -d pokerbot_dev

# Для Railway БД (используйте данные из DATABASE_URL)
psql "postgresql://username:password@host:port/database"
```

### Сброс локальной базы данных
```bash
dropdb pokerbot_dev
createdb pokerbot_dev
```

### Просмотр логов
```bash
# В отдельном терминале
tail -f bot.log
```

## 🚨 Важные моменты

1. **Разные токены**: Используйте тестовый токен бота для локальной разработки
2. **Webhook vs Polling**: Локально используйте polling, на Railway - webhook
3. **База данных**: Локальная БД не влияет на продакшн данные
4. **Пароли игр**: В локальной версии можно использовать простые пароли для тестирования

## 🧪 Тестирование

1. Создайте тестового бота через @BotFather
2. Используйте `/start` для регистрации
3. Протестируйте все команды
4. Проверьте работу с базой данных

## 📝 Отладка

### Проблемы с подключением к БД
```bash
# Проверьте статус PostgreSQL
brew services list | grep postgresql

# Проверьте подключение
psql -d pokerbot_dev -c "SELECT version();"
```

### Проблемы с токеном
- Убедитесь, что токен правильный
- Проверьте, что бот не заблокирован
- Используйте разные токены для локальной и продакшн версий

## 🎯 Следующие шаги

После настройки локальной разработки:
1. Протестируйте новые функции локально
2. Создайте отдельную ветку для разработки
3. Протестируйте изменения
4. Деплойте на Railway только после тестирования 