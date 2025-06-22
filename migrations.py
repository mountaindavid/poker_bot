#!/usr/bin/env python3
"""
Database migrations for PokerBot
Handles safe database schema updates
"""

import psycopg2
import logging
from datetime import datetime
from bot import get_db_connection, _get_connection_params

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self):
        self.connection = get_db_connection()
        self.cursor = self.connection.cursor()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()
        self.connection.close()
        
    def create_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        ''')
        self.connection.commit()
        
    def migration_applied(self, migration_name):
        """Check if migration was already applied"""
        self.cursor.execute(
            "SELECT id FROM migrations WHERE migration_name = %s", 
            (migration_name,)
        )
        return self.cursor.fetchone() is not None
        
    def mark_migration_applied(self, migration_name, description=""):
        """Mark migration as applied"""
        self.cursor.execute(
            "INSERT INTO migrations (migration_name, description) VALUES (%s, %s)",
            (migration_name, description)
        )
        self.connection.commit()
        
    def run_migration(self, migration_name, sql_commands, description=""):
        """Run a migration if it hasn't been applied yet"""
        if self.migration_applied(migration_name):
            logger.info(f"Migration {migration_name} already applied, skipping")
            return
            
        logger.info(f"Applying migration: {migration_name}")
        
        try:
            for sql in sql_commands:
                self.cursor.execute(sql)
                logger.info(f"Executed: {sql[:50]}...")
                
            self.connection.commit()
            self.mark_migration_applied(migration_name, description)
            logger.info(f"Migration {migration_name} applied successfully")
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Migration {migration_name} failed: {e}")
            raise

def run_all_migrations():
    """Run all pending migrations"""
    with DatabaseMigrator() as migrator:
        migrator.create_migrations_table()
        
        # Migration 1: Add new fields to players table
        migrator.run_migration(
            "add_player_stats_fields",
            [
                "ALTER TABLE players ADD COLUMN IF NOT EXISTS total_rebuys NUMERIC(10,1) DEFAULT 0.0",
                "ALTER TABLE players ADD COLUMN IF NOT EXISTS last_game_date TIMESTAMP",
                "ALTER TABLE players ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"
            ],
            "Add total_rebuys, last_game_date, and is_active fields to players table"
        )
        
        # Migration 2: Add indexes for better performance
        migrator.run_migration(
            "add_performance_indexes",
            [
                "CREATE INDEX IF NOT EXISTS idx_transactions_game_id ON transactions(game_id)",
                "CREATE INDEX IF NOT EXISTS idx_transactions_player_id ON transactions(player_id)",
                "CREATE INDEX IF NOT EXISTS idx_games_active ON games(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_players_telegram_id ON players(telegram_id)"
            ],
            "Add performance indexes for better query speed"
        )
        
        # Migration 3: Add constraints for data integrity
        migrator.run_migration(
            "add_data_constraints",
            [
                "ALTER TABLE transactions ADD CONSTRAINT check_type_valid CHECK (type IN ('buyin', 'rebuy', 'cashout'))"
            ],
            "Add constraints to ensure data integrity"
        )
        
        # Migration 4: Add new table for game history
        migrator.run_migration(
            "create_game_history_table",
            [
                '''
                CREATE TABLE IF NOT EXISTS game_history (
                    id SERIAL PRIMARY KEY,
                    game_id INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    action_type VARCHAR(50) NOT NULL,
                    amount NUMERIC(10,1),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
                    FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
                )
                ''',
                "CREATE INDEX IF NOT EXISTS idx_game_history_game_id ON game_history(game_id)",
                "CREATE INDEX IF NOT EXISTS idx_game_history_player_id ON game_history(player_id)"
            ],
            "Create game_history table for detailed game tracking"
        )

def rollback_migration(migration_name):
    """Rollback a specific migration (use with caution!)"""
    with DatabaseMigrator() as migrator:
        if not migrator.migration_applied(migration_name):
            logger.warning(f"Migration {migration_name} was not applied")
            return
            
        logger.warning(f"Rolling back migration: {migration_name}")
        
        # Define rollback SQL for each migration
        rollback_sql = {
            "add_player_stats_fields": [
                "ALTER TABLE players DROP COLUMN IF EXISTS total_rebuys",
                "ALTER TABLE players DROP COLUMN IF EXISTS last_game_date", 
                "ALTER TABLE players DROP COLUMN IF EXISTS is_active"
            ],
            "add_performance_indexes": [
                "DROP INDEX IF EXISTS idx_transactions_game_id",
                "DROP INDEX IF EXISTS idx_transactions_player_id",
                "DROP INDEX IF EXISTS idx_games_active",
                "DROP INDEX IF EXISTS idx_players_telegram_id"
            ],
            "add_data_constraints": [
                "ALTER TABLE transactions DROP CONSTRAINT IF EXISTS check_amount_positive",
                "ALTER TABLE transactions DROP CONSTRAINT IF EXISTS check_type_valid"
            ],
            "create_game_history_table": [
                "DROP TABLE IF EXISTS game_history CASCADE"
            ]
        }
        
        if migration_name in rollback_sql:
            try:
                for sql in rollback_sql[migration_name]:
                    migrator.cursor.execute(sql)
                    logger.info(f"Rolled back: {sql[:50]}...")
                    
                migrator.connection.commit()
                
                # Remove migration record
                migrator.cursor.execute(
                    "DELETE FROM migrations WHERE migration_name = %s",
                    (migration_name,)
                )
                migrator.connection.commit()
                
                logger.info(f"Migration {migration_name} rolled back successfully")
                
            except Exception as e:
                migrator.connection.rollback()
                logger.error(f"Rollback of {migration_name} failed: {e}")
                raise
        else:
            logger.error(f"No rollback SQL defined for migration {migration_name}")

def show_migration_status():
    """Show which migrations have been applied"""
    with DatabaseMigrator() as migrator:
        migrator.cursor.execute("""
            SELECT migration_name, applied_at, description 
            FROM migrations 
            ORDER BY applied_at
        """)
        migrations = migrator.cursor.fetchall()
        
        if not migrations:
            print("No migrations have been applied yet.")
            return
            
        print("Applied migrations:")
        print("-" * 80)
        for name, applied_at, description in migrations:
            print(f"✅ {name}")
            print(f"   Applied: {applied_at}")
            print(f"   Description: {description}")
            print()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "migrate":
            run_all_migrations()
        elif command == "rollback" and len(sys.argv) > 2:
            rollback_migration(sys.argv[2])
        elif command == "status":
            show_migration_status()
        else:
            print("Usage:")
            print("  python migrations.py migrate    # Run all pending migrations")
            print("  python migrations.py rollback <migration_name>  # Rollback specific migration")
            print("  python migrations.py status     # Show migration status")
    else:
        run_all_migrations() 