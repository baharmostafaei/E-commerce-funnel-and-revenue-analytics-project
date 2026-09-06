import pandas as pd 
import numpy as np 
dim_users = pd.read_csv("./exports/dim_users.csv") 
dim_channel = pd.read_csv("./exports/dim_marketing_channel.csv") 
rng = np.random.default_rng(seed=42) 
n_users = len(dim_users) 
channel_choice = rng.choice( dim_channel["channel_id"], size=n_users, p=dim_channel["acquisition_weight"] ) 
dim_users["acquisition_channel_id"] = channel_choice 
print(dim_users.head())  
print(dim_users["acquisition_channel_id"].value_counts(normalize=True).sort_index())

dim_users.to_csv("./exports/dim_users.csv", index=False) 
print("updated dim_users saved!")