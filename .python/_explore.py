import pandas as pd
orders = pd.read_csv("./data/raw/olist_orders_dataset.csv", 
        parse_dates=["order_purchase_timestamp",                                                                   
                     "order_delivered_carrier_date",
                     "order_delivered_customer_date",
                     "order_estimated_delivery_date"])

print(orders.dtypes)

customers = pd.read_csv("./data/raw/olist_customers_dataset.csv") 
print("customers:", customers.shape) 
print(customers.head(3)) 
items = pd.read_csv("./data/raw/olist_order_items_dataset.csv") 
print("items:", items.shape) 
print(items.head(3)) 
payments = pd.read_csv("./data/raw/olist_order_payments_dataset.csv") 
print("payments:", payments.shape) 
print(payments.head(3)) 
products = pd.read_csv("./data/raw/olist_products_dataset.csv") 
print("products:", products.shape) 
print(products.head(3))