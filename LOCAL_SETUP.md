# 🏠 Локальный запуск PokerBot

## 📋 Предварительные требования

### 1. Python 3.8+
```bash
python3 --version
```

### 2. PostgreSQL
Установите PostgreSQL на вашу систему:

**macOS (с Homebrew):**
```bash
brew install postgresql
brew services start postgresql
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
Скачайте с [официального сайта](https://www.postgresql.org/download/windows/)

### 3. Telegram Bot Token
1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям для создания бота
4. Скопируйте полученный токен

## 🚀 Пошаговая настройка

### Шаг 1: Клонирование и настройка окружения
```bash
# Активируйте виртуальное окружение
source .venv/bin/activate  # macOS/Linux
# или
.venv\Scripts\activate     # Windows

# Установите зависимости
pip install -r requirements.txt
```

### Шаг 2: Настройка базы данных
```bash
# Подключитесь к PostgreSQL
sudo -u postgres psql

# Создайте пользователя и базу данных
CREATE USER pokerbot WITH PASSWORD 'your_password';
CREATE DATABASE pokerbot_dev OWNER pokerbot;
GRANT ALL PRIVILEGES ON DATABASE pokerbot_dev TO pokerbot;
\q
```

### Шаг 3: Создание файла конфигурации
```bash
# Скопируйте пример конфигурации
cp env.example .env

# Отредактируйте .env файл
nano .env  # или используйте любой текстовый редактор
```

**Содержимое .env файла:**
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here

# Database Configuration
PGHOST=localhost
PGPORT=5432
PGUSER=pokerbot
PGPASSWORD=your_password
PGDATABASE=pokerbot_dev

# Local Development
PORT=5000
```

### Шаг 4: Запуск бота

**Вариант 1: Локальный режим (рекомендуется для разработки)**
```bash
python run_local.py
```

**Вариант 2: Webhook режим (для тестирования webhook)**
```bash
python main.py
```

## 🧪 Тестирование

1. Найдите вашего бота в Telegram
2. Отправьте `/start` для регистрации
3. Отправьте `/menu` для просмотра команд
4. Протестируйте создание игры: `/new_game`

## 🔧 Устранение неполадок

### Ошибка подключения к базе данных
```bash
# Проверьте статус PostgreSQL
sudo systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS

# Проверьте подключение
psql -h localhost -U pokerbot -d pokerbot_dev
```

### Ошибка с токеном бота
- Убедитесь, что токен правильный
- Проверьте, что бот не заблокирован
- Попробуйте создать нового бота через @BotFather

### Проблемы с зависимостями
```bash
# Обновите pip
pip install --upgrade pip

# Переустановите зависимости
pip uninstall -r requirements.txt
pip install -r requirements.txt
```

## 📝 Полезные команды

### Просмотр логов
```bash
# В отдельном терминале
tail -f bot.log  # если настроено логирование в файл
```

### Остановка бота
```bash
# Нажмите Ctrl+C в терминале где запущен бот
```

### Сброс базы данных
```bash
# В PostgreSQL
DROP DATABASE pokerbot_dev;
CREATE DATABASE pokerbot_dev OWNER pokerbot;
```

## 🎯 Следующие шаги

После успешного локального запуска:
1. Протестируйте все функции бота
2. Настройте webhook для продакшена
3. Разверните на Railway/Heroku
4. Настройте мониторинг и логирование

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи в консоли
2. Убедитесь, что все переменные окружения настроены
3. Проверьте подключение к базе данных
4. Создайте issue в репозитории 