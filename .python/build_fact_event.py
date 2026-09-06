import pandas as pd
import numpy as np

fact_orders = pd.read_csv("./exports/fact_orders.csv")
dim_users= pd.read_csv("./exports/dim_users.csv")
dim_channels = pd.read_csv("./exports/dim_marketing_channel.csv")

STAGES = ["session_start", "product_view", "add_to_cart", "checkout_start", "purchase"] 
STAGE_RATE = {"session_start": 1.00, "product_view": 0.70, "add_to_cart": 0.35, "checkout_start": 0.20, "purchase": 0.12} 

n_purchases= len(fact_orders)
total_sessions= int(round(n_purchases / STAGE_RATE["purchase"]))
stage_counts= {s: int(round(total_sessions * r)) for s, r in STAGE_RATE.items()}
stage_counts["purchase"] = n_purchases


rng = np.random.default_rng(seed=42) 
orders_raw = pd.read_csv("./data/raw/olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"]) 
purchase_ts_map = orders_raw.set_index("order_id")["order_purchase_timestamp"] 
purchase_sessions = fact_orders[["order_id", "user_key", "channel_id"]].copy() 
purchase_sessions["session_id"] = "S-" + purchase_sessions["order_id"] 
purchase_sessions["purchase_ts"] = purchase_sessions["order_id"].map(purchase_ts_map) 


STAGE_GAP_MIN = { "session_start": (2, 15), 
                 "product_view": (5, 30), 
                 "add_to_cart": (3, 20), 
                 "checkout_start": (2, 15), 
                } 
n = len(purchase_sessions) 
cur_ts = purchase_sessions["purchase_ts"].values 
stage_timestamps = {"purchase": cur_ts} 
for i in range(len(STAGES) - 1, 0, -1):
    stage_name = STAGES[i - 1]
    lo, hi = STAGE_GAP_MIN[stage_name]
    gap_minutes = rng.integers(lo, hi + 1, size=n)
    cur_ts = cur_ts - pd.to_timedelta(gap_minutes, unit="m")
    stage_timestamps[stage_name] = cur_ts

for s in STAGES:
    print(s, stage_timestamps[s][0])

extra_needed = { "checkout_start": stage_counts["checkout_start"] - stage_counts["purchase"],
                 "add_to_cart": stage_counts["add_to_cart"] - stage_counts["checkout_start"],
                 "product_view": stage_counts["product_view"] - stage_counts["add_to_cart"], 
                 "session_start": stage_counts["session_start"] - stage_counts["product_view"],
                } 

def build_backward_timestamps(anchor_ts, stage_idx_end):
    n = len(anchor_ts)
    ts_by_stage = {STAGES[stage_idx_end]: anchor_ts}
    cur = anchor_ts
    for i in range(stage_idx_end, 0, -1):
        stage_name = STAGES[i - 1]
        lo, hi = STAGE_GAP_MIN[stage_name]
        gap_minutes = rng.integers(lo, hi + 1, size=n)
        cur = cur - pd.to_timedelta(gap_minutes, unit="m")
        ts_by_stage[stage_name] = cur
    return ts_by_stage

date_pool = orders_raw["order_purchase_timestamp"].values 
channel_ids = dim_channels["channel_id"].values 
channel_weights = dim_channels["acquisition_weight"].values 
user_pool = dim_users["user_key"].values 

all_nonconverted = []

for furthest_stage, n in extra_needed.items():
    if n <= 0:
        continue
    stage_idx = STAGES.index(furthest_stage)

    sampled_dates = pd.to_datetime(rng.choice(date_pool, size=n)).normalize()
    minute_of_day = rng.integers(0, 24 * 60, size=n)
    anchor_ts = sampled_dates + pd.to_timedelta(minute_of_day, unit="m")

    sampled_channels = rng.choice(channel_ids, size=n, p=channel_weights)
    sampled_users = rng.choice(user_pool, size=n)

    ts_by_stage = build_backward_timestamps(anchor_ts, stage_idx)
    session_ids = [f"NC-{furthest_stage[:2]}-{i}" for i in range(n)]

    for s in STAGES[:stage_idx + 1]:
        df = pd.DataFrame({
            "session_id": session_ids,
            "user_key": sampled_users,
            "channel_id": sampled_channels,
            "stage": s,
            "stage_timestamp": ts_by_stage[s],
        })
        all_nonconverted.append(df)

nonconverted = pd.concat(all_nonconverted, ignore_index=True)
print("Non-converted event rows:", len(nonconverted))
print(nonconverted.head())


converted_rows = [] 
for s in STAGES: 
    df = pd.DataFrame({ 
        "session_id": purchase_sessions["session_id"], 
        "user_key": purchase_sessions["user_key"], 
        "channel_id": purchase_sessions["channel_id"], 
        "stage": s, 
        "stage_timestamp": stage_timestamps[s], 
        }) 
    converted_rows.append(df) 
    
converted = pd.concat(converted_rows, ignore_index=True) 
print("Converted event rows:", len(converted))

fact_events = pd.concat([converted, nonconverted], ignore_index=True) 
stage_order_map = {s: i + 1 for i, s in enumerate(STAGES)} 
fact_events["stage_order"] = fact_events["stage"].map(stage_order_map) 
fact_events["date_key"] = pd.to_datetime(fact_events["stage_timestamp"]).dt.strftime("%Y%m%d").astype(int) 
print("Final fact_events rows:", len(fact_events)) 
print(fact_events.head()) 

print(fact_events["stage"].value_counts()) 
fact_events.to_csv("./exports/fact_events.csv", index=False) 
print("saved!")