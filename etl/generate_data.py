import csv
import random
import os
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
os.makedirs(RAW_DIR, exist_ok=True)

CATEGORIES = {
    'Electronics': ['Smartphones', 'Laptops', 'Tablets', 'Headphones', 'Cameras'],
    'Clothing': ['T-Shirts', 'Jeans', 'Jackets', 'Shoes', 'Accessories'],
    'Home & Kitchen': ['Furniture', 'Appliances', 'Cookware', 'Bedding', 'Lighting'],
    'Books': ['Fiction', 'Non-Fiction', 'Academic', 'Comics', 'Reference'],
    'Sports': ['Cricket', 'Football', 'Gym Equipment', 'Running', 'Swimming'],
    'Beauty': ['Skincare', 'Makeup', 'Haircare', 'Fragrances', 'Wellness'],
    'Automotive': ['Car Parts', 'Bike Accessories', 'Oil & Fluids', 'Tyres', 'Tools'],
    'Grocery': ['Snacks', 'Beverages', 'Dairy', 'Staples', 'Organic'],
    'Toys': ['Board Games', 'Action Figures', 'Puzzles', 'Dolls', 'Outdoor'],
    'Health': ['Supplements', 'First Aid', 'Monitors', 'PPE', 'Devices'],
}

REGIONS = {
    'North': ['Delhi', 'Jaipur', 'Lucknow', 'Chandigarh', 'Amritsar'],
    'South': ['Chennai', 'Bangalore', 'Hyderabad', 'Kochi', 'Coimbatore'],
    'East': ['Kolkata', 'Bhubaneswar', 'Patna', 'Guwahati', 'Ranchi'],
    'West': ['Mumbai', 'Pune', 'Ahmedabad', 'Surat', 'Indore'],
    'Central': ['Bhopal', 'Nagpur', 'Raipur', 'Jabalpur', 'Varanasi'],
}

WAREHOUSES = [
    ('WH-Delhi', 'Delhi', 'North', 15000),
    ('WH-Mumbai', 'Mumbai', 'West', 20000),
    ('WH-Chennai', 'Chennai', 'South', 12000),
    ('WH-Kolkata', 'Kolkata', 'East', 10000),
    ('WH-Bangalore', 'Bangalore', 'South', 18000),
]

CARRIERS = ['BlueDart', 'DTDC', 'Delhivery', 'Ecom Express', 'India Post', 'FedEx', 'DHL']
PAYMENT_METHODS = ['cod', 'online', 'online', 'online', 'bank_transfer']
ORDER_STATUSES = ['pending', 'processing', 'shipped', 'delivered', 'delivered', 'delivered', 'cancelled']


def generate_products(n=500):
    products = []
    all_subcats = []
    for cat, subcats in CATEGORIES.items():
        for s in subcats:
            all_subcats.append((cat, s))

    for i in range(1, n + 1):
        cat, subcat = random.choice(all_subcats)
        price = round(random.uniform(99, 15000), 2)
        cost = round(price * random.uniform(0.4, 0.75), 2)
        weight = round(random.uniform(0.1, 25.0), 2)
        products.append([
            i,
            fake.catch_phrase()[:200],
            cat,
            subcat,
            price,
            cost,
            weight,
            random.choices([1, 0], weights=[90, 10])[0]
        ])
    return products


def generate_suppliers(n=50):
    suppliers = []
    for i in range(1, n + 1):
        region = random.choice(list(REGIONS.keys()))
        city = random.choice(REGIONS[region])
        suppliers.append([
            i,
            fake.company()[:200],
            fake.name(),
            fake.email(),
            fake.phone_number()[:20],
            region,
            city,
            'India',
            round(random.uniform(2.0, 5.0), 1),
            random.choices([1, 0], weights=[85, 15])[0]
        ])
    return suppliers


def generate_customers(n=1000):
    customers = []
    for i in range(1, n + 1):
        region = random.choice(list(REGIONS.keys()))
        city = random.choice(REGIONS[region])
        ctype = random.choices(['individual', 'business'], weights=[70, 30])[0]
        customers.append([
            i,
            fake.first_name(),
            fake.last_name(),
            fake.email(),
            fake.phone_number()[:20],
            city,
            region,
            ctype
        ])
    return customers


def generate_inventory(products, warehouses):
    inventory = []
    inv_id = 1
    for wh in warehouses:
        wh_products = random.sample(products, k=min(350, len(products)))
        for p in wh_products:
            qty = random.randint(0, 400)
            reorder = random.choice([20, 30, 50, 75, 100])
            inventory.append([
                inv_id,
                p[0],
                warehouses.index(wh) + 1,
                qty,
                reorder,
                max(reorder * 5, qty + 100),
                fake.date_time_between(start_date='-6M', end_date='now').strftime('%Y-%m-%d %H:%M:%S')
            ])
            inv_id += 1
    return inventory


def generate_orders(customers, warehouses, n=10000):
    orders = []
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 12, 31)

    for i in range(1, n + 1):
        cust = random.choice(customers)
        wh = random.choice(warehouses)
        order_date = fake.date_between(start_date=start_date, end_date=end_date)
        status = random.choice(ORDER_STATUSES)
        payment = random.choice(PAYMENT_METHODS)
        discount = round(random.choice([0, 0, 0, 2.5, 5.0, 7.5, 10.0, 15.0]), 2)

        orders.append([
            i,
            cust[0],
            warehouses.index(wh) + 1,
            order_date.strftime('%Y-%m-%d'),
            status,
            0.00,
            discount,
            0.00,
            payment
        ])
    return orders


def generate_order_items(orders, products, n_items=25000):
    items = []
    item_id = 1
    used_combos = set()

    for _ in range(n_items):
        order = random.choice(orders)
        product = random.choice(products)
        key = (order[0], product[0])

        if key in used_combos:
            continue
        used_combos.add(key)

        qty = random.randint(1, 10)
        price = product[4]
        items.append([
            item_id,
            order[0],
            product[0],
            qty,
            price
        ])
        item_id += 1

    return items


def generate_shipments(orders, warehouses):
    shipments = []
    ship_id = 1
    shipped_orders = [o for o in orders if o[4] in ('shipped', 'delivered', 'cancelled')]

    for order in shipped_orders:
        wh = random.choice(warehouses)
        ship_date = datetime.strptime(order[3], '%Y-%m-%d') + timedelta(days=random.randint(0, 3))
        del_date = ship_date + timedelta(days=random.randint(2, 10)) if order[4] == 'delivered' else None
        status = 'delivered' if order[4] == 'delivered' else ('in_transit' if order[4] == 'shipped' else 'returned')

        shipments.append([
            ship_id,
            order[0],
            warehouses.index(wh) + 1,
            ship_date.strftime('%Y-%m-%d'),
            del_date.strftime('%Y-%m-%d') if del_date else None,
            random.choice(CARRIERS),
            f"TRK{random.randint(10000000, 99999999)}",
            status,
            round(random.uniform(30, 500), 2)
        ])
        ship_id += 1

    return shipments


def generate_product_suppliers(products, suppliers):
    ps = []
    for p in products:
        n_suppliers = random.randint(1, 3)
        chosen = random.sample(suppliers, k=min(n_suppliers, len(suppliers)))
        for idx, s in enumerate(chosen):
            supply_price = round(p[4] * random.uniform(0.35, 0.7), 2)
            ps.append([
                p[0],
                s[0],
                supply_price,
                random.choice([3, 5, 7, 10, 14]),
                1 if idx == 0 else 0
            ])
    return ps


def write_csv(filename, headers, data):
    path = os.path.join(RAW_DIR, filename)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    print(f"  Created {filename}: {len(data)} records")


if __name__ == '__main__':
    print("Generating DataFusion seed data...\n")

    products = generate_products(500)
    write_csv('products.csv',
              ['product_id', 'product_name', 'category', 'subcategory', 'unit_price',
               'cost_price', 'weight_kg', 'is_active'],
              products)

    suppliers = generate_suppliers(50)
    write_csv('suppliers.csv',
              ['supplier_id', 'supplier_name', 'contact_person', 'email', 'phone',
               'region', 'city', 'country', 'rating', 'is_active'],
              suppliers)

    customers = generate_customers(1000)
    write_csv('customers.csv',
              ['customer_id', 'first_name', 'last_name', 'email', 'phone',
               'city', 'region', 'customer_type'],
              customers)

    write_csv('warehouses.csv',
              ['warehouse_id', 'warehouse_name', 'city', 'region', 'capacity_units', 'is_active'],
              [[i + 1, w[0], w[1], w[2], w[3], 1] for i, w in enumerate(WAREHOUSES)])

    inventory = generate_inventory(products, WAREHOUSES)
    write_csv('inventory.csv',
              ['inventory_id', 'product_id', 'warehouse_id', 'quantity',
               'reorder_level', 'max_stock', 'last_restocked'],
              inventory)

    orders = generate_orders(customers, WAREHOUSES, 10000)
    write_csv('orders.csv',
              ['order_id', 'customer_id', 'warehouse_id', 'order_date', 'status',
               'total_amount', 'discount_pct', 'final_amount', 'payment_method'],
              orders)

    items = generate_order_items(orders, products, 25000)
    write_csv('order_items.csv',
              ['item_id', 'order_id', 'product_id', 'quantity', 'unit_price'],
              items)

    shipments = generate_shipments(orders, WAREHOUSES)
    write_csv('shipments.csv',
              ['shipment_id', 'order_id', 'warehouse_id', 'shipped_date',
               'delivered_date', 'carrier', 'tracking_number', 'status', 'shipping_cost'],
              shipments)

    ps = generate_product_suppliers(products, suppliers)
    write_csv('product_suppliers.csv',
              ['product_id', 'supplier_id', 'supply_price', 'lead_time_days', 'is_preferred'],
              ps)

    print("\nDone! All CSV files created in data/raw/")
