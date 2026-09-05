import pandas as pd 
dim_channel = pd.DataFrame([ {"channel_id": 1, "channel_name": "Organic Search", "channel_type": "Organic", "avg_cost_per_session": 0.00, "acquisition_weight": 0.22}, 
                            {"channel_id": 2, "channel_name": "Paid Search", "channel_type": "Paid", "avg_cost_per_session": 1.85, "acquisition_weight": 0.20}, 
                            {"channel_id": 3, "channel_name": "Paid Social", "channel_type": "Paid", "avg_cost_per_session": 1.35, "acquisition_weight": 0.18}, 
                            {"channel_id": 4, "channel_name": "Email", "channel_type": "Owned", "avg_cost_per_session": 0.05, "acquisition_weight": 0.12}, 
                            {"channel_id": 5, "channel_name": "Direct", "channel_type": "Organic", "avg_cost_per_session": 0.00, "acquisition_weight": 0.16}, 
                            {"channel_id": 6, "channel_name": "Referral", "channel_type": "Organic", "avg_cost_per_session": 0.20, "acquisition_weight": 0.12}, ]) 
print("Total weight:", dim_channel["acquisition_weight"].sum()) 
print(dim_channel) 
dim_channel.to_csv("./exports/dim_marketing_channel.csv", index=False) 
print("saved!")