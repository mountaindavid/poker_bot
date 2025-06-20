# 🔄 Руководство по миграциям базы данных

## 📋 Что такое миграции?

Миграции - это способ безопасного обновления структуры базы данных без потери данных. Они позволяют:
- ✅ Добавлять новые поля и таблицы
- ✅ Изменять существующие структуры
- ✅ Откатывать изменения при необходимости
- ✅ Отслеживать историю изменений

## 🚀 Как использовать миграции

### **1. Локальная разработка**

```bash
# Запустить все миграции
python migrations.py migrate

# Проверить статус миграций
python migrations.py status

# Откатить конкретную миграцию (осторожно!)
python migrations.py rollback add_player_stats_fields
```

### **2. На Railway (продакшн)**

#### **Вариант A: Автоматические миграции**
Миграции запускаются автоматически при старте приложения через `init_db()`.

#### **Вариант B: Ручные миграции**
```bash
# Подключитесь к Railway через CLI или SSH
railway login
railway link
railway shell

# Запустите миграции
python migrations.py migrate
```

## 📝 Создание новой миграции

### **1. Добавьте новую миграцию в `migrations.py`:**

```python
# В функции run_all_migrations()
migrator.run_migration(
    "your_migration_name",
    [
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS new_field VARCHAR(100)",
        "UPDATE players SET new_field = 'default_value' WHERE new_field IS NULL"
    ],
    "Description of what this migration does"
)
```

### **2. Добавьте rollback SQL:**

```python
# В словаре rollback_sql
"your_migration_name": [
    "ALTER TABLE players DROP COLUMN IF EXISTS new_field"
]
```

## 🔧 Типичные сценарии миграций

### **Добавление нового поля**
```sql
-- Миграция
ALTER TABLE players ADD COLUMN IF NOT EXISTS phone VARCHAR(20);

-- Rollback
ALTER TABLE players DROP COLUMN IF EXISTS phone;
```

### **Изменение типа поля**
```sql
-- Миграция (создаем новое поле, копируем данные, удаляем старое)
ALTER TABLE players ADD COLUMN new_field INTEGER;
UPDATE players SET new_field = CAST(old_field AS INTEGER);
ALTER TABLE players DROP COLUMN old_field;
ALTER TABLE players RENAME COLUMN new_field TO old_field;

-- Rollback (обратная операция)
ALTER TABLE players ADD COLUMN old_field TEXT;
UPDATE players SET old_field = CAST(new_field AS TEXT);
ALTER TABLE players DROP COLUMN new_field;
ALTER TABLE players RENAME COLUMN old_field TO new_field;
```

### **Добавление индекса**
```sql
-- Миграция
CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);

-- Rollback
DROP INDEX IF EXISTS idx_players_name;
```

### **Добавление ограничения**
```sql
-- Миграция
ALTER TABLE players ADD CONSTRAINT check_name_length CHECK (LENGTH(name) > 0);

-- Rollback
ALTER TABLE players DROP CONSTRAINT IF EXISTS check_name_length;
```

## ⚠️ Важные правила

### **1. Безопасность данных**
- ✅ Всегда используйте `IF NOT EXISTS` и `IF EXISTS`
- ✅ Делайте резервную копию перед миграцией
- ✅ Тестируйте миграции на локальной копии данных

### **2. Именование**
- ✅ Используйте описательные имена миграций
- ✅ Включайте дату в имя для сложных миграций
- ✅ Пример: `add_player_stats_2024_01_15`

### **3. Rollback**
- ✅ Всегда пишите rollback SQL
- ✅ Тестируйте rollback на локальных данных
- ✅ Учитывайте зависимости между миграциями

## 🚨 Опасные операции

### **Удаление полей/таблиц**
```sql
-- Очень осторожно! Может потерять данные
ALTER TABLE players DROP COLUMN field_name;
DROP TABLE table_name;
```

### **Изменение первичных ключей**
```sql
-- Требует особой осторожности
ALTER TABLE players DROP CONSTRAINT players_pkey;
ALTER TABLE players ADD PRIMARY KEY (new_field);
```

## 📊 Мониторинг миграций

### **Проверка статуса**
```bash
python migrations.py status
```

### **Просмотр в базе данных**
```sql
SELECT * FROM migrations ORDER BY applied_at DESC;
```

### **Логи Railway**
```bash
railway logs
# Ищите сообщения о миграциях
```

## 🔄 Workflow для изменений

### **1. Разработка**
```bash
# 1. Создайте новую миграцию
# 2. Протестируйте локально
python migrations.py migrate
python migrations.py status

# 3. Проверьте rollback
python migrations.py rollback your_migration_name
python migrations.py migrate  # Применить снова
```

### **2. Продакшн**
```bash
# 1. Сделайте резервную копию
railway backup

# 2. Деплойте код с миграциями
git push railway main

# 3. Проверьте логи
railway logs

# 4. Проверьте статус
railway shell
python migrations.py status
```

### **3. Откат (если что-то пошло не так)**
```bash
# 1. Откатите миграцию
railway shell
python migrations.py rollback problematic_migration

# 2. Или откатите весь деплой
railway rollback
```

## 📞 Поддержка

Если миграция не работает:
1. Проверьте логи Railway
2. Убедитесь, что SQL синтаксис правильный
3. Проверьте права доступа к базе данных
4. Создайте issue с описанием проблемы

## 🎯 Лучшие практики

1. **Тестируйте миграции** на копии продакшн данных
2. **Делайте резервные копии** перед каждой миграцией
3. **Используйте транзакции** для сложных миграций
4. **Документируйте изменения** в комментариях
5. **Планируйте rollback** заранее
6. **Мониторьте производительность** после миграций 