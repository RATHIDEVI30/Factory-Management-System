import sqlite3
from datetime import datetime, timedelta
import random
import os

db_path = os.path.join('instance', 'kks_factory.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Clear existing data to make it look clean and then seed it
cursor.execute("DELETE FROM producer_request")
cursor.execute("DELETE FROM production")
cursor.execute("DELETE FROM sale")
cursor.execute("DELETE FROM inventory")

# Seed Inventory
cursor.execute("INSERT INTO inventory (item_name, quantity, unit) VALUES ('Raw Cassava', 15000.0, 'Kg')")
cursor.execute("INSERT INTO inventory (item_name, quantity, unit) VALUES ('Finished Sago', 5500.0, 'Kg')")

# Seed Producer Data (2 years of data for previous year + current year analytics)
producers = ['Ravi Kumar', 'Murugan', 'Selvam', 'Prakash', 'Kumaravel', 'Ramesh', 'Arumugam', 'Senthil', 
             'Velu', 'Kannan', 'Balan', 'Mani', 'Ganesan', 'Suresh', 'Dinesh', 'Rajesh', 'Vignesh', 'Prabhu']
address_base = 'Salem District'

end_date = datetime.now()
start_date = end_date - timedelta(days=730) # 2 years

# Helper to generate a date only in allowed months and never in the future
def get_seasonal_date():
    while True:
        year = random.randint(2024, 2026)
        month = random.choice([1, 2, 3, 12])
        day = random.randint(1, 28)
        hour = random.randint(8, 17)
        minute = random.randint(0, 59)
        dt = datetime(year, month, day, hour, minute)
        if dt <= datetime.now():
            return dt

# Seed Producer Requests (Procurement)
# Generate ~800 requests to simulate high volume of small scale farmers
for _ in range(800):
    date = get_seasonal_date()
    producer = random.choice(producers)
    
    # 70% chance of small quantity (1, 5, 20 packets), 30% chance of large quantity
    if random.random() < 0.7:
        quantity = random.randint(2, 40)
    else:
        quantity = random.randint(100, 500)
    
    packet_size = 25.0
    price_per_packet = round(random.uniform(250, 400), 2)
    total_amount = quantity * price_per_packet
    status = random.choice(['Approved', 'Paid', 'Paid', 'Paid', 'Pending'])
    
    cursor.execute('''
        INSERT INTO producer_request (name, phone, quantity, packet_size, price_per_packet, total_amount, address, date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (producer, f'+91 {random.randint(9000000000, 9999999999)}', quantity, packet_size, price_per_packet, total_amount, address_base, date.strftime('%Y-%m-%d %H:%M:%S'), status))

# Seed Production
# ~300 production runs
for _ in range(300):
    date = get_seasonal_date()
    input_qty = random.randint(1000, 15000)
    output_qty = input_qty * 0.35
    cost = input_qty * 2.5 # approx cost
    status = 'Completed'

    cursor.execute('''
        INSERT INTO production (date, input_qty, output_qty, cost, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (date.strftime('%Y-%m-%d %H:%M:%S'), input_qty, output_qty, cost, status))

# Seed Sales
# ~400 sales
agents = ['Global Sago Traders']
for _ in range(400):
    date = get_seasonal_date()
    quantity = random.randint(500, 5000)  # kg
    rate = round(random.uniform(40, 60), 2)
    total_amount = quantity * rate
    agent_name = random.choice(agents)

    cursor.execute('''
        INSERT INTO sale (date, quantity, rate, total_amount, agent_name)
        VALUES (?, ?, ?, ?, ?)
    ''', (date.strftime('%Y-%m-%d %H:%M:%S'), quantity, rate, total_amount, agent_name))

conn.commit()
conn.close()
print("Database successfully seeded with highly realistic fake data!")
