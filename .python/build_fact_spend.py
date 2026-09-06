import pandas as pd 
import numpy as np 

rng = np.random.default_rng(seed=42) 
fact_events = pd.read_csv("./exports/fact_events.csv") 
dim_channel = pd.read_csv("./exports/dim_marketing_channel.csv") 
sessions = fact_events[fact_events["stage"] == "session_start"].copy() 
sessions["year_month"] = sessions["date_key"].astype(str).str[:6] 
sessions["year_month"] = sessions["year_month"].str[:4] + "-" + sessions["year_month"].str[4:] 
spend_agg = sessions.groupby(["channel_id", "year_month"]).size().reset_index(name="sessions") 
spend_agg = spend_agg.merge(dim_channel[["channel_id", "avg_cost_per_session"]], on="channel_id") 

noise = rng.uniform(0.85, 1.15, size=len(spend_agg)) 
spend_agg["spend_amount"] = (spend_agg["sessions"] * spend_agg["avg_cost_per_session"] * noise).round(2) 
fact_channel_spend = spend_agg[["channel_id", "year_month", "sessions", "spend_amount"]] 
print(fact_channel_spend.shape) 
print(fact_channel_spend.head(10)) 
fact_channel_spend.to_csv("./exports/fact_channel_spend.csv", index=False) 
print("saved!")