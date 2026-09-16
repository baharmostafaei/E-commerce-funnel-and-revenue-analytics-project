import os
import pandas as pd
import numpy as np


# ============================================================
# Configuration
# ============================================================
RANDOM_SEED = 42

FACT_ORDERS_PATH = "./exports/fact_orders.csv"
DIM_USERS_PATH = "./exports/dim_users.csv"
DIM_CHANNELS_PATH = "./exports/dim_marketing_channel.csv"
ORDERS_RAW_PATH = "./data/raw/olist_orders_dataset.csv"
OUTPUT_PATH = "./exports/fact_events.csv"

STAGES = [
    "session_start",
    "product_view",
    "add_to_cart",
    "checkout_start",
    "purchase",
]

# IMPORTANT:
# These are CUMULATIVE reach rates from session_start, not step-to-step rates.
# Example: purchase=0.16 means 16% of all sessions for that channel purchase.
# The values are synthetic by design because Olist does not contain web-event
# or acquisition-channel data.
CHANNEL_FUNNEL_RATE = {
    "Organic Search": {
        "session_start": 1.00,
        "product_view": 0.76,
        "add_to_cart": 0.42,
        "checkout_start": 0.24,
        "purchase": 0.135,
    },
    "Paid Search": {
        "session_start": 1.00,
        "product_view": 0.72,
        "add_to_cart": 0.35,
        "checkout_start": 0.20,
        "purchase": 0.110,
    },
    "Paid Social": {
        "session_start": 1.00,
        "product_view": 0.68,
        "add_to_cart": 0.30,
        "checkout_start": 0.16,
        "purchase": 0.095,
    },
    "Email": {
        "session_start": 1.00,
        "product_view": 0.82,
        "add_to_cart": 0.50,
        "checkout_start": 0.32,
        "purchase": 0.160,
    },
    "Direct": {
        "session_start": 1.00,
        "product_view": 0.75,
        "add_to_cart": 0.40,
        "checkout_start": 0.23,
        "purchase": 0.125,
    },
    "Referral": {
        "session_start": 1.00,
        "product_view": 0.73,
        "add_to_cart": 0.37,
        "checkout_start": 0.21,
        "purchase": 0.115,
    },
}

# Minutes between a stage and the next stage.
# When timestamps are generated backwards from the furthest reached stage,
# the key below identifies the earlier stage.
STAGE_GAP_MIN = {
    "session_start": (2, 15),
    "product_view": (5, 30),
    "add_to_cart": (3, 20),
    "checkout_start": (2, 15),
}

STAGE_CODE = {
    "session_start": "SS",
    "product_view": "PV",
    "add_to_cart": "ATC",
    "checkout_start": "CO",
    "purchase": "PU",
}


# ============================================================
# Helpers
# ============================================================
def validate_funnel_config():
    """Validate that every channel has a monotonic cumulative funnel."""
    for channel_name, rates in CHANNEL_FUNNEL_RATE.items():
        missing = [stage for stage in STAGES if stage not in rates]
        if missing:
            raise ValueError(
                f"Missing funnel rates for {channel_name}: {missing}"
            )

        values = [rates[stage] for stage in STAGES]

        if rates["session_start"] != 1.0:
            raise ValueError(
                f"session_start must be 1.0 for {channel_name}."
            )

        if any(rate <= 0 or rate > 1 for rate in values):
            raise ValueError(
                f"All funnel rates must be in (0, 1] for {channel_name}."
            )

        if any(values[i] < values[i + 1] for i in range(len(values) - 1)):
            raise ValueError(
                f"Funnel rates must be non-increasing for {channel_name}: {rates}"
            )


def build_backward_timestamps(anchor_ts, stage_idx_end, rng):
    """
    Build timestamps backwards from the furthest stage reached.

    Example:
      stage_idx_end = 2 means the session reached add_to_cart.
      We create timestamps for session_start, product_view and add_to_cart.
    """
    anchor_ts = pd.to_datetime(anchor_ts)
    n = len(anchor_ts)

    ts_by_stage = {STAGES[stage_idx_end]: anchor_ts}
    current_ts = anchor_ts

    for i in range(stage_idx_end, 0, -1):
        earlier_stage = STAGES[i - 1]
        lo, hi = STAGE_GAP_MIN[earlier_stage]

        gap_minutes = rng.integers(lo, hi + 1, size=n)
        current_ts = current_ts - pd.to_timedelta(gap_minutes, unit="m")
        ts_by_stage[earlier_stage] = current_ts

    return ts_by_stage


def make_random_anchor_timestamps(date_pool, n, rng):
    """Sample dates and random times within each sampled date."""
    if n <= 0:
        return pd.DatetimeIndex([])

    sampled_dates = pd.to_datetime(
        rng.choice(date_pool, size=n, replace=True)
    ).normalize()

    minute_of_day = rng.integers(0, 24 * 60, size=n)

    return sampled_dates + pd.to_timedelta(minute_of_day, unit="m")


def build_stage_counts(purchase_count, rates):
    """
    Derive target session/stage counts for one channel from its actual
    purchase count and configured cumulative funnel rates.
    """
    purchase_rate = rates["purchase"]

    total_sessions = max(
        purchase_count,
        int(round(purchase_count / purchase_rate)),
    )

    stage_counts = {
        "session_start": total_sessions,
        "product_view": int(round(total_sessions * rates["product_view"])),
        "add_to_cart": int(round(total_sessions * rates["add_to_cart"])),
        "checkout_start": int(round(total_sessions * rates["checkout_start"])),
        # Purchases come from the real fact_orders table, so preserve them exactly.
        "purchase": int(purchase_count),
    }

    counts = [stage_counts[stage] for stage in STAGES]
    if any(counts[i] < counts[i + 1] for i in range(len(counts) - 1)):
        raise ValueError(
            "Generated stage counts are not monotonic. "
            f"purchase_count={purchase_count}, rates={rates}, counts={stage_counts}"
        )

    return stage_counts


# ============================================================
# Load data
# ============================================================
validate_funnel_config()
rng = np.random.default_rng(seed=RANDOM_SEED)

fact_orders = pd.read_csv(FACT_ORDERS_PATH)
dim_users = pd.read_csv(DIM_USERS_PATH)
dim_channels = pd.read_csv(DIM_CHANNELS_PATH)
orders_raw = pd.read_csv(
    ORDERS_RAW_PATH,
    parse_dates=["order_purchase_timestamp"],
)

required_fact_order_cols = {"order_id", "user_key", "channel_id"}
required_dim_user_cols = {"user_key", "acquisition_channel_id"}
required_dim_channel_cols = {"channel_id", "channel_name"}

if not required_fact_order_cols.issubset(fact_orders.columns):
    raise ValueError(
        f"fact_orders is missing columns: "
        f"{required_fact_order_cols - set(fact_orders.columns)}"
    )

if not required_dim_user_cols.issubset(dim_users.columns):
    raise ValueError(
        "dim_users must contain acquisition_channel_id. "
        "Run assign_channels.py before this script."
    )

if not required_dim_channel_cols.issubset(dim_channels.columns):
    raise ValueError(
        f"dim_marketing_channel is missing columns: "
        f"{required_dim_channel_cols - set(dim_channels.columns)}"
    )

# Normalize key dtypes.
fact_orders["channel_id"] = pd.to_numeric(
    fact_orders["channel_id"], errors="raise"
).astype(int)

dim_channels["channel_id"] = pd.to_numeric(
    dim_channels["channel_id"], errors="raise"
).astype(int)

dim_users["acquisition_channel_id"] = pd.to_numeric(
    dim_users["acquisition_channel_id"], errors="raise"
).astype(int)

# Make sure every configured channel exists in dim_marketing_channel.
channel_name_to_id = dict(
    zip(dim_channels["channel_name"], dim_channels["channel_id"])
)

missing_channels = set(CHANNEL_FUNNEL_RATE) - set(channel_name_to_id)
if missing_channels:
    raise ValueError(
        "These configured channels are missing from dim_marketing_channel: "
        f"{sorted(missing_channels)}"
    )

# Make sure every purchase/order has a configured channel.
configured_channel_ids = {
    channel_name_to_id[channel_name]
    for channel_name in CHANNEL_FUNNEL_RATE
}

unexpected_channel_ids = (
    set(fact_orders["channel_id"].dropna().unique()) - configured_channel_ids
)
if unexpected_channel_ids:
    raise ValueError(
        "fact_orders contains channel_id values with no funnel configuration: "
        f"{sorted(unexpected_channel_ids)}"
    )


# ============================================================
# Build purchase sessions from real orders
# ============================================================
purchase_ts_map = orders_raw.set_index("order_id")["order_purchase_timestamp"]

purchase_sessions = fact_orders[["order_id", "user_key", "channel_id"]].copy()
purchase_sessions["session_id"] = "S-" + purchase_sessions["order_id"].astype(str)
purchase_sessions["purchase_ts"] = purchase_sessions["order_id"].map(purchase_ts_map)

if purchase_sessions["purchase_ts"].isna().any():
    missing_count = int(purchase_sessions["purchase_ts"].isna().sum())
    raise ValueError(
        f"Could not map purchase timestamp for {missing_count} fact_orders rows."
    )

# All converted sessions contain all five funnel stages.
purchase_stage_timestamps = build_backward_timestamps(
    purchase_sessions["purchase_ts"].to_numpy(),
    STAGES.index("purchase"),
    rng,
)

converted_rows = []

for stage in STAGES:
    converted_rows.append(
        pd.DataFrame(
            {
                "session_id": purchase_sessions["session_id"].to_numpy(),
                "user_key": purchase_sessions["user_key"].to_numpy(),
                "channel_id": purchase_sessions["channel_id"].to_numpy(),
                "stage": stage,
                "stage_timestamp": purchase_stage_timestamps[stage],
            }
        )
    )

converted = pd.concat(converted_rows, ignore_index=True)


# ============================================================
# Build channel-specific non-converted sessions
# ============================================================
all_nonconverted = []
all_user_pool = dim_users["user_key"].dropna().to_numpy()
global_date_pool = purchase_sessions["purchase_ts"].dropna().to_numpy()

channel_target_summary = []

for channel_name, rates in CHANNEL_FUNNEL_RATE.items():
    channel_id = channel_name_to_id[channel_name]

    channel_purchases = purchase_sessions[
        purchase_sessions["channel_id"] == channel_id
    ].copy()

    purchase_count = len(channel_purchases)

    if purchase_count == 0:
        print(f"WARNING: {channel_name} has 0 purchases; skipping.")
        continue

    stage_counts = build_stage_counts(purchase_count, rates)

    channel_target_summary.append(
        {
            "channel_id": channel_id,
            "channel_name": channel_name,
            **{f"target_{stage}": stage_counts[stage] for stage in STAGES},
        }
    )

    # Number of sessions whose furthest reached stage is each non-purchase stage.
    extra_needed = {
        "checkout_start": (
            stage_counts["checkout_start"] - stage_counts["purchase"]
        ),
        "add_to_cart": (
            stage_counts["add_to_cart"] - stage_counts["checkout_start"]
        ),
        "product_view": (
            stage_counts["product_view"] - stage_counts["add_to_cart"]
        ),
        "session_start": (
            stage_counts["session_start"] - stage_counts["product_view"]
        ),
    }

    # Keep synthetic non-converted traffic temporally similar to purchases from
    # the same channel. Fall back to all purchase dates if needed.
    channel_date_pool = channel_purchases["purchase_ts"].dropna().to_numpy()
    if len(channel_date_pool) == 0:
        channel_date_pool = global_date_pool

    # Prefer sampling users whose assigned acquisition channel matches the
    # session channel. Fall back to the complete user pool if necessary.
    channel_user_pool = dim_users.loc[
        dim_users["acquisition_channel_id"] == channel_id,
        "user_key",
    ].dropna().to_numpy()

    if len(channel_user_pool) == 0:
        channel_user_pool = all_user_pool

    for furthest_stage, n_extra in extra_needed.items():
        n_extra = int(n_extra)

        if n_extra <= 0:
            continue

        stage_idx = STAGES.index(furthest_stage)

        anchor_ts = make_random_anchor_timestamps(
            channel_date_pool,
            n_extra,
            rng,
        )

        sampled_users = rng.choice(
            channel_user_pool,
            size=n_extra,
            replace=True,
        )

        ts_by_stage = build_backward_timestamps(
            anchor_ts,
            stage_idx,
            rng,
        )

        stage_code = STAGE_CODE[furthest_stage]
        session_ids = [
            f"NC-C{channel_id}-{stage_code}-{i:07d}"
            for i in range(n_extra)
        ]

        for stage in STAGES[: stage_idx + 1]:
            all_nonconverted.append(
                pd.DataFrame(
                    {
                        "session_id": session_ids,
                        "user_key": sampled_users,
                        "channel_id": channel_id,
                        "stage": stage,
                        "stage_timestamp": ts_by_stage[stage],
                    }
                )
            )


if all_nonconverted:
    nonconverted = pd.concat(all_nonconverted, ignore_index=True)
else:
    nonconverted = pd.DataFrame(
        columns=[
            "session_id",
            "user_key",
            "channel_id",
            "stage",
            "stage_timestamp",
        ]
    )


# ============================================================
# Final fact_events table
# ============================================================
fact_events = pd.concat(
    [converted, nonconverted],
    ignore_index=True,
)

stage_order_map = {stage: i + 1 for i, stage in enumerate(STAGES)}
fact_events["stage_order"] = fact_events["stage"].map(stage_order_map)

fact_events["stage_timestamp"] = pd.to_datetime(
    fact_events["stage_timestamp"]
)

fact_events["date_key"] = (
    fact_events["stage_timestamp"]
    .dt.strftime("%Y%m%d")
    .astype(int)
)

# Keep IDs numeric/consistent where possible.
fact_events["channel_id"] = pd.to_numeric(
    fact_events["channel_id"], errors="raise"
).astype(int)

# Sort for readability and reproducibility.
fact_events = fact_events.sort_values(
    ["session_id", "stage_order"],
    kind="stable",
).reset_index(drop=True)


# ============================================================
# Validation
# ============================================================
# A session should appear at most once at each stage.
duplicate_session_stage = int(
    fact_events.duplicated(["session_id", "stage"]).sum()
)

if duplicate_session_stage != 0:
    raise ValueError(
        f"Found {duplicate_session_stage} duplicate session-stage rows."
    )

# Every fact_order must still correspond to exactly one purchase session.
actual_purchase_sessions = fact_events.loc[
    fact_events["stage"] == "purchase",
    "session_id",
].nunique()

expected_purchase_sessions = len(purchase_sessions)

if actual_purchase_sessions != expected_purchase_sessions:
    raise ValueError(
        "Purchase session count mismatch: "
        f"expected={expected_purchase_sessions:,}, "
        f"actual={actual_purchase_sessions:,}"
    )

# Channel-level validation table.
stage_by_channel = (
    fact_events.groupby(["channel_id", "stage"])["session_id"]
    .nunique()
    .unstack(fill_value=0)
    .reindex(columns=STAGES, fill_value=0)
    .reset_index()
)

stage_by_channel = stage_by_channel.merge(
    dim_channels[["channel_id", "channel_name"]],
    on="channel_id",
    how="left",
)

stage_by_channel["actual_conversion_rate"] = (
    stage_by_channel["purchase"]
    / stage_by_channel["session_start"]
)

stage_by_channel["view_rate"] = (
    stage_by_channel["product_view"]
    / stage_by_channel["session_start"]
)

stage_by_channel["view_to_cart_rate"] = (
    stage_by_channel["add_to_cart"]
    / stage_by_channel["product_view"]
)

stage_by_channel["cart_to_checkout_rate"] = (
    stage_by_channel["checkout_start"]
    / stage_by_channel["add_to_cart"]
)

stage_by_channel["checkout_to_purchase_rate"] = (
    stage_by_channel["purchase"]
    / stage_by_channel["checkout_start"]
)

# Add configured target conversion rate for easy comparison.
stage_by_channel["target_conversion_rate"] = stage_by_channel[
    "channel_name"
].map(
    {
        channel_name: rates["purchase"]
        for channel_name, rates in CHANNEL_FUNNEL_RATE.items()
    }
)

stage_by_channel = stage_by_channel[
    [
        "channel_id",
        "channel_name",
        "session_start",
        "product_view",
        "add_to_cart",
        "checkout_start",
        "purchase",
        "view_rate",
        "view_to_cart_rate",
        "cart_to_checkout_rate",
        "checkout_to_purchase_rate",
        "actual_conversion_rate",
        "target_conversion_rate",
    ]
].sort_values("actual_conversion_rate", ascending=False)


# ============================================================
# Save
# ============================================================
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
fact_events.to_csv(OUTPUT_PATH, index=False)

print("\n" + "=" * 72)
print("FACT EVENTS CREATED SUCCESSFULLY")
print("=" * 72)
print(f"Converted event rows:     {len(converted):,}")
print(f"Non-converted event rows: {len(nonconverted):,}")
print(f"Total event rows:         {len(fact_events):,}")
print(f"Unique sessions:          {fact_events['session_id'].nunique():,}")
print(f"Purchase sessions:        {actual_purchase_sessions:,}")

print("\nOverall stage counts:")
print(
    fact_events.groupby("stage")["session_id"]
    .nunique()
    .reindex(STAGES)
    .to_string()
)

print("\nChannel funnel validation:")
validation_print = stage_by_channel.copy()

for col in [
    "view_rate",
    "view_to_cart_rate",
    "cart_to_checkout_rate",
    "checkout_to_purchase_rate",
    "actual_conversion_rate",
    "target_conversion_rate",
]:
    validation_print[col] = (validation_print[col] * 100).round(2).astype(str) + "%"

print(validation_print.to_string(index=False))

print(f"\nSaved to: {OUTPUT_PATH}")
print("\nNEXT STEPS:")
print("1) Run build_fact_spend.py again (spend depends on session counts).")
print("2) Run loud_to_sql.py again to replace fact_events and fact_channel_spend in PostgreSQL.")
print("3) Refresh the Power BI model.")
