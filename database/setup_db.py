'''import sqlite3

def setup_database():
    conn = sqlite3.connect("database/db.sqlite3")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        quantity_sold INTEGER,
        sale_date DATE
    )
    """)

    cursor.execute("DELETE FROM sales_records")
    sample_data = [
        ("Apple", 100, "2025-05-01"),
        ("Banana", 150, "2025-05-02"),
        ("Orange", 120, "2025-05-03")
    ]
    cursor.executemany("""
        INSERT INTO sales_records (product_name, quantity_sold, sale_date)
        VALUES (?, ?, ?)""", sample_data)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_database()'''

import sqlite3
from datetime import datetime, timedelta
import random
import os

def setup_database():
    # Ensure the 'database' directory exists
    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect("database/db.sqlite3")
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product TEXT,
        quantity INTEGER,
        amount REAL,
        sale_date TEXT
    )
    ''')

    cursor.execute('DELETE FROM sales')

    products = ["Apples", "Bananas", "Oranges", "Grapes", "Mangoes"]
    start_date = datetime.strptime("2024-01-01", "%Y-%m-%d")
    days = 365

    for i in range(days):
        current_date = start_date + timedelta(days=i)
        for _ in range(random.randint(3, 6)):
            product = random.choice(products)
            quantity = random.randint(10, 100)
            price_per_unit = random.uniform(1.0, 5.0)
            amount = round(quantity * price_per_unit, 2)

            cursor.execute('''
            INSERT INTO sales (product, quantity, amount, sale_date)
            VALUES (?, ?, ?, ?)
            ''', (product, quantity, amount, current_date.strftime("%Y-%m-%d")))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_database()
