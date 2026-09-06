import pandas as pd 
items = pd.read_csv("./data/raw/olist_order_items_dataset.csv")

item_agg = items.groupby("order_id").agg(
    num_items = ("order_item_id", "count"),
    total_price = ("price", "sum"), 
    total_freight = ("freight_value", "sum")
).reset_index()

payments = pd.read_csv("./data/raw/olist_order_payments_dataset.csv") 

pay_agg = payments.groupby("order_id").agg(
    total_payment_value = ("payment_value", "sum"),
    payment_type= ("payment_type", 
                   lambda s: s.value_counts().idxmax()
                   ),
).reset_index()

orders= pd.read_csv("./data/raw/olist_orders_dataset.csv", 
                    parse_dates=["order_purchase_timestamp", 
                                 "order_delivered_customer_date", 
                                 "order_estimated_delivery_date" ])

customers= pd.read_csv("./data/raw/olist_customers_dataset.csv")

orders= orders.merge(customers[["customer_id", "customer_unique_id"]], 
                     on= "customer_id",
                     how= "inner")

orders= orders.merge(item_agg, 
                     on="order_id", 
                     how="left")

orders = orders.merge(pay_agg, 
                      on= "order_id", 
                      how="left")
dim_users = pd.read_csv("./exports/dim_users.csv")
orders= orders.merge(dim_users[["user_key", "customer_unique_id", "acquisition_channel_id"]],
                     on= "customer_unique_id", 
                     how= "inner")

orders= orders.rename(columns={"acquisition_channel_id": "channel_id"})

print("orders after merging with dim_users:", orders.shape)

orders["date_key"] = orders["order_purchase_timestamp"].dt.strftime("%Y%m%d").astype(int) 
orders["delivery_days"] = (orders["order_delivered_customer_date"] - orders["order_purchase_timestamp"]).dt.days 

fact_orders = orders[[ "order_id", "user_key", "channel_id", "date_key", "order_status", "num_items", "total_price", 
                       "total_freight", "total_payment_value", "payment_type", "delivery_days" ]] 

print("fact_orders final:", fact_orders.shape) 

print(fact_orders.head()) 

print(" null in each column:") 

print(fact_orders.isna().sum()) 

fact_orders.to_csv("./exports/fact_orders.csv", index=False) 
print("saved!")

