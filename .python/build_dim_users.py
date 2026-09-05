import pandas as pd
orders = pd.read_csv("./data/raw/olist_orders_dataset.csv", parse_dates= ["order_purchase_timestamp"])
customers= pd.read_csv("./data/raw/olist_customers_dataset.csv")

orders_with_geo = orders.merge(customers, on="customer_id", how="inner")

print("merge:", orders_with_geo.shape) 

print(orders_with_geo[["order_id", "customer_id", "customer_unique_id"]].head())

dim_users = (orders_with_geo .sort_values("order_purchase_timestamp") 
            .groupby("customer_unique_id") 
            .agg(first_order_date=("order_purchase_timestamp", "first"), 
            customer_state=("customer_state", "first"), 
            customer_city=("customer_city", "first"), 
            ) 
            .reset_index() ) 
print("dim_users shape:", dim_users.shape) 
print(dim_users.head())

dim_users["user_key"] = range(1, len(dim_users) + 1) 

dim_users = dim_users[["user_key", "customer_unique_id", "first_order_date", "customer_state", "customer_city"]] 

print(dim_users.head()) 

print(dim_users["user_key"].is_unique) 

import os 

os.makedirs("./exports", exist_ok=True) 

dim_users.to_csv("./exports/dim_users.csv", index=False) 
print("saved!")