import pandas as pd
items = pd.read_csv("./data/raw/olist_order_items_dataset.csv") 

orders = pd.read_csv("./data/raw/olist_orders_dataset.csv", 
                     parse_dates=["order_purchase_timestamp"]) 

customers = pd.read_csv("./data/raw/olist_customers_dataset.csv") 

dim_users = pd.read_csv("./exports/dim_users.csv") 

dim_products = pd.read_csv("./exports/dim_products.csv")

items = items.merge(orders[["order_id", "customer_id", "order_purchase_timestamp"]],
                    on="order_id", 
                    how="inner")

items = items.merge(customers[["customer_id", "customer_unique_id"]], 
                    on="customer_id", 
                    how="inner") 

print("after 1st merge: ", items.shape)

items = items.merge(dim_users[["user_key", "customer_unique_id"]], on="customer_unique_id", how="inner")
items = items.merge(dim_products[["product_key", "product_id"]], on="product_id", how="inner") 
items["date_key"] = items["order_purchase_timestamp"].dt.strftime("%Y%m%d").astype(int) 

fact_order_items = items[[ "order_id", "order_item_id", "user_key", "product_key", "seller_id", "date_key", "price", "freight_value" ]] 

print("fact_order_items final:", fact_order_items.shape) 

print(fact_order_items.head()) 

fact_order_items.to_csv("./exports/fact_order_items.csv", index=False) 

print("saved!")