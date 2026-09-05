import pandas as pd 
orders = pd.read_csv("./data/raw/olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"])

date_min = orders["order_purchase_timestamp"].min().normalize()
date_max = orders["order_purchase_timestamp"].max().normalize()

dim_date = pd.DataFrame({"full_date": pd.date_range(date_min, date_max, freq="D")})
print("number of days:", len(dim_date))

dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)

dim_date["year"] = dim_date["full_date"].dt.year
dim_date["month"] = dim_date["full_date"].dt.month
dim_date["year_month"] = dim_date["full_date"].dt.strftime("%Y-%m")

dim_date["quarter"] = dim_date["full_date"].dt.quarter

dim_date["day_of_week"] = dim_date["full_date"].dt.day_name()
dim_date["is_weekend"] = dim_date["full_date"].dt.dayofweek >= 5

print(dim_date.head()) 
print(dim_date["date_key"].is_unique)