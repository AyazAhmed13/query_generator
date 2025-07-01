import sqlite3
from datetime import datetime, timedelta
import random
import os

def setup_car_sales_database():
    # Ensure the 'database' directory exists
    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect("database/car_sales.sqlite3")
    cursor = conn.cursor()

    # Create the car_sales table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS car_sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        car_brand TEXT,
        car_model TEXT,
        country TEXT,
        quantity INTEGER,
        amount REAL,
        sale_date TEXT
    )
    ''')

    # Clear previous data if any
    cursor.execute('DELETE FROM car_sales')

    car_brands_models = {
        "Toyota": ["Corolla", "Camry", "RAV4"],
        "Ford": ["F-150", "Mustang", "Explorer"],
        "BMW": ["3 Series", "X5", "Z4"],
        "Hyundai": ["Elantra", "Tucson", "Santa Fe"],
        "Tesla": ["Model S", "Model 3", "Model Y"]
    }

    countries = ["USA", "Germany", "India", "Japan", "Brazil", "UK", "Canada", "Australia"]
    start_date = datetime.strptime("2024-05-01", "%Y-%m-%d")
    days = 365

    for i in range(days):
        current_date = start_date + timedelta(days=i)
        for _ in range(random.randint(4, 8)):
            brand = random.choice(list(car_brands_models.keys()))
            model = random.choice(car_brands_models[brand])
            country = random.choice(countries)
            quantity = random.randint(1, 10)
            price_per_unit = random.uniform(20000, 80000)
            amount = round(quantity * price_per_unit, 2)

            cursor.execute('''
            INSERT INTO car_sales (car_brand, car_model, country, quantity, amount, sale_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (brand, model, country, quantity, amount, current_date.strftime("%Y-%m-%d")))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_car_sales_database()
