import os
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine

load_dotenv()

password= os.getenv("DB_PASSWORD")

engine= create_engine(f"postgresql+psycopg2://postgres:{password}@127.0.0.1:5432/ecommerce_analytics")
tables= ["dim_date", "dim_users", "dim_products", "dim_marketing_channel", "fact_orders", "fact_order_items", "fact_events", "fact_channel_spend"]
for name in tables: 
    df = pd.read_csv(f"./exports/{name}.csv") 
    df.to_sql(name, engine, if_exists="replace", index=False, chunksize=10000, method="multi") 
    print(f"loaded {name}: {len(df)} rows")

print("ALL DONE")