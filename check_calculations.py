#!/usr/bin/env python3
"""
Quick check of calculations after fixing duplicate transaction
"""

import os
import psycopg2
from urllib.parse import urlparse

def get_db_connection():
    """Get database connection using DATABASE_URL or local settings"""
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Parse DATABASE_URL for Railway
        parsed = urlparse(database_url)
        conn_params = {
            'host': parsed.hostname,
            'port': parsed.port,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path[1:],  # Remove leading slash
            'sslmode': 'require' if parsed.scheme == 'postgresql' else 'disable'
        }
    else:
        # Local development
        conn_params = {
            'host': os.getenv("PGHOST", "localhost"),
            'port': int(os.getenv("PGPORT", "5432")),
            'user': os.getenv("PGUSER", "postgres"),
            'password': os.getenv("PGPASSWORD", "0000"),
            'database': os.getenv("PGDATABASE", "pokerbot_dev"),
            'sslmode': "disable"
        }
    
    # For local development, always disable SSL
    if not database_url or 'localhost' in conn_params.get('host', ''):
        conn_params['sslmode'] = 'disable'
    
    return psycopg2.connect(**conn_params)

def check_calculations():
    """Check if calculations are correct after fix"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("🔍 Checking calculations after fix...")
        print("=" * 80)
        
        # Check David's transactions specifically
        cursor.execute("""
            SELECT id, game_id, amount, type, created_at 
            FROM transactions 
            WHERE player_id = 1 
            ORDER BY id
        """)
        
        transactions = cursor.fetchall()
        print("📋 David's transactions:")
        print("-" * 50)
        for tx_id, game_id, amount, tx_type, created_at in transactions:
            print(f"ID {tx_id}: {amount} ({tx_type}) - Game {game_id}")
        
        # Calculate totals for David
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'buyin' THEN ABS(amount) ELSE 0 END), 0) as total_buyins,
                COALESCE(SUM(CASE WHEN type = 'rebuy' THEN ABS(amount) ELSE 0 END), 0) as total_rebuys,
                COALESCE(SUM(CASE WHEN type = 'cashout' THEN amount ELSE 0 END), 0) as total_cashouts
            FROM transactions 
            WHERE player_id = 1
        """)
        
        result = cursor.fetchone()
        if result:
            total_buyins, total_rebuys, total_cashouts = result
            profit = total_cashouts - (total_buyins + total_rebuys)
            
            print(f"\n💰 David's calculation:")
            print(f"   Buy-ins: {total_buyins:.1f}")
            print(f"   Rebuys: {total_rebuys:.1f}")
            print(f"   Cashouts: {total_cashouts:.1f}")
            print(f"   Profit: {'+' if profit > 0 else ''}{profit:.1f}")
            
            # Check if it matches expected values
            expected_buyins = 40.0
            expected_cashouts = 180.3
            expected_profit = 140.3
            
            print(f"\n✅ Verification:")
            print(f"   Expected buy-ins: {expected_buyins} | Actual: {total_buyins} | {'✅' if total_buyins == expected_buyins else '❌'}")
            print(f"   Expected cashouts: {expected_cashouts} | Actual: {total_cashouts} | {'✅' if total_cashouts == expected_cashouts else '❌'}")
            print(f"   Expected profit: {expected_profit} | Actual: {profit} | {'✅' if abs(profit - expected_profit) < 0.1 else '❌'}")
        
        # Check all players
        cursor.execute("""
            SELECT name, 
                   COALESCE(SUM(CASE WHEN t.type = 'buyin' THEN ABS(t.amount) ELSE 0 END), 0) as total_buyins,
                   COALESCE(SUM(CASE WHEN t.type = 'rebuy' THEN ABS(t.amount) ELSE 0 END), 0) as total_rebuys,
                   COALESCE(SUM(CASE WHEN t.type = 'cashout' THEN t.amount ELSE 0 END), 0) as total_cashouts
            FROM players p
            LEFT JOIN transactions t ON t.player_id = p.id
            GROUP BY p.id, p.name
            ORDER BY p.name
        """)
        
        results = cursor.fetchall()
        print(f"\n📊 All players summary:")
        print("-" * 80)
        print(f"{'Name':<15} | {'Buy-ins':<10} | {'Rebuys':<10} | {'Cashouts':<10} | {'Profit':<10}")
        print("-" * 80)
        
        total_profit = 0
        for name, buyins, rebuys, cashouts in results:
            profit = cashouts - (buyins + rebuys)
            profit_str = f"{'+' if profit > 0 else ''}{profit:.1f}"
            print(f"{name:<15} | {buyins:<10.1f} | {rebuys:<10.1f} | {cashouts:<10.1f} | {profit_str:<10}")
            total_profit += profit
        
        print("-" * 80)
        total_profit_str = f"{'+' if total_profit > 0 else ''}{total_profit:.1f}"
        print(f"{'TOTAL':<15} | {'':<10} | {'':<10} | {'':<10} | {total_profit_str:<10}")
        
        print(f"\n🎉 All calculations look correct!")
        
    except Exception as e:
        print(f"❌ Error checking calculations: {e}")
        print(f"Database URL: {os.getenv('DATABASE_URL', 'Not set')}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_calculations() 