import sqlite3
from datetime import datetime, timedelta
import random

# Create database
conn = sqlite3.connect('ecommerce.db')
cursor = conn.cursor()

# Drop existing tables if they exist
cursor.execute('DROP TABLE IF EXISTS order_items')
cursor.execute('DROP TABLE IF EXISTS orders')
cursor.execute('DROP TABLE IF EXISTS products')
cursor.execute('DROP TABLE IF EXISTS customers')

# 1. Create Customers Table
cursor.execute('''
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
''')

# 2. Create Products Table
cursor.execute('''
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock_quantity INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
''')

# 3. Create Orders Table (with FK to customers)
cursor.execute('''
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL,
    shipping_address TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
)
''')

# 4. Create Order Items Table (with FK to orders and products)
cursor.execute('''
CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
)
''')

print("✓ Tables created successfully!")

# ===== INSERT SAMPLE DATA =====

# Insert Customers
customers_data = [
    ('John Smith', 'john.smith@email.com', '+1-555-0101', 'USA', 'New York'),
    ('Emma Wilson', 'emma.wilson@email.com', '+1-555-0102', 'USA', 'Los Angeles'),
    ('Mohammed Al-Rashid', 'mohammed@email.com', '+971-555-0103', 'UAE', 'Dubai'),
    ('Priya Sharma', 'priya.sharma@email.com', '+91-555-0104', 'India', 'Mumbai'),
    ('Carlos Rodriguez', 'carlos.r@email.com', '+52-555-0105', 'Mexico', 'Mexico City'),
    ('Li Wei', 'li.wei@email.com', '+86-555-0106', 'China', 'Shanghai'),
    ('Sarah Johnson', 'sarah.j@email.com', '+44-555-0107', 'UK', 'London'),
    ('Yuki Tanaka', 'yuki.t@email.com', '+81-555-0108', 'Japan', 'Tokyo'),
    ('Anna Mueller', 'anna.m@email.com', '+49-555-0109', 'Germany', 'Berlin'),
    ('Lucas Silva', 'lucas.s@email.com', '+55-555-0110', 'Brazil', 'Sao Paulo')
]

cursor.executemany('''
    INSERT INTO customers (name, email, phone, country, city)
    VALUES (?, ?, ?, ?, ?)
''', customers_data)

print(f"✓ Inserted {len(customers_data)} customers")

# Insert Products
products_data = [
    ('iPhone 15 Pro', 'Electronics', 999.99, 50),
    ('Samsung Galaxy S24', 'Electronics', 899.99, 45),
    ('MacBook Pro 16"', 'Electronics', 2499.99, 30),
    ('Dell XPS 15', 'Electronics', 1799.99, 35),
    ('Sony WH-1000XM5', 'Audio', 399.99, 100),
    ('AirPods Pro', 'Audio', 249.99, 150),
    ('iPad Air', 'Electronics', 599.99, 60),
    ('Apple Watch Series 9', 'Wearables', 429.99, 80),
    ('Nike Air Max', 'Fashion', 129.99, 200),
    ('Adidas Ultraboost', 'Fashion', 189.99, 150),
    ('Levi\'s 501 Jeans', 'Fashion', 69.99, 300),
    ('The North Face Jacket', 'Fashion', 299.99, 100),
    ('Kindle Paperwhite', 'Electronics', 139.99, 120),
    ('Fitbit Charge 6', 'Wearables', 179.99, 90),
    ('Bose SoundLink', 'Audio', 149.99, 75)
]

cursor.executemany('''
    INSERT INTO products (product_name, category, price, stock_quantity)
    VALUES (?, ?, ?, ?)
''', products_data)

print(f"✓ Inserted {len(products_data)} products")

# Insert Orders with Order Items
order_statuses = ['Completed', 'Pending', 'Shipped', 'Delivered', 'Cancelled']
base_date = datetime.now() - timedelta(days=90)

order_id = 1
for _ in range(50):  # Create 50 orders
    customer_id = random.randint(1, 10)
    order_date = (base_date + timedelta(days=random.randint(0, 90))).strftime('%Y-%m-%d')
    status = random.choice(order_statuses)
    
    # Random number of items per order (1-4)
    num_items = random.randint(1, 4)
    total_amount = 0
    order_items = []
    
    for _ in range(num_items):
        product_id = random.randint(1, 15)
        quantity = random.randint(1, 3)
        
        # Get product price
        cursor.execute('SELECT price FROM products WHERE product_id = ?', (product_id,))
        unit_price = cursor.fetchone()[0]
        subtotal = unit_price * quantity
        total_amount += subtotal
        
        order_items.append((order_id, product_id, quantity, unit_price, subtotal))
    
    # Insert order
    cursor.execute('''
        INSERT INTO orders (customer_id, order_date, total_amount, status, shipping_address)
        VALUES (?, ?, ?, ?, ?)
    ''', (customer_id, order_date, round(total_amount, 2), status, f'Address {customer_id}'))
    
    # Insert order items
    cursor.executemany('''
        INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal)
        VALUES (?, ?, ?, ?, ?)
    ''', order_items)
    
    order_id += 1

print(f"✓ Inserted 50 orders with order items")

# Commit and close
conn.commit()
conn.close()

print("\n" + "="*60)
print("✅ DATABASE CREATED SUCCESSFULLY!")
print("="*60)
print("\nDatabase file: ecommerce.db")
print("\nTables created:")
print("  1. customers (10 records)")
print("  2. products (15 records)")
print("  3. orders (50 records)")
print("  4. order_items (~100+ records)")
print("\nForeign Key Relationships:")
print("  • orders.customer_id → customers.customer_id")
print("  • order_items.order_id → orders.order_id")
print("  • order_items.product_id → products.product_id")
print("\n" + "="*60)

# Print sample queries to test
print("\nSample questions to test in VoiceSQL:")
print("  1. 'Show me all customers from USA'")
print("  2. 'What are the total sales by country?'")
print("  3. 'Show me all orders with customer names'")
print("  4. 'Which products were ordered by customers from India?'")
print("  5. 'What is the most popular product category?'")
print("  6. 'Show customers who spent more than $1000'")
print("="*60)