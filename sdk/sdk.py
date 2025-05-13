# ───────────────────────────────────────────────
# Imports & Page Config  (config = FIRST st.*!)
# ───────────────────────────────────────────────
import streamlit as st
st.set_page_config(page_title="ACM Guild Admin",
                   page_icon="🛠️",
                   layout="centered")

import os
import json
from dotenv import load_dotenv
import boto3
import pandas as pd

# ───────────────────────────────────────────────
# AWS / S3 Helpers
# ───────────────────────────────────────────────
load_dotenv()
REGION  = "us-east-2"
BUCKET  = "acm-github-data"
aws_key = os.getenv("AWS_ACCESS_KEY")
aws_secret = os.getenv("AWS_SECRET")

s3 = boto3.client("s3",
    region_name=REGION,
    aws_access_key_id=aws_key,
    aws_secret_access_key=aws_secret,
)

def fetch_json(key: str):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception as exc:
        st.error(f"Error fetching {key}: {exc}")
        return []

def upload_json(key: str, data):
    s3.put_object(Bucket=BUCKET,
                  Key=key,
                  Body=json.dumps(data, indent=4).encode("utf-8"))

# ───────────────────────────────────────────────
# Business Logic
# ───────────────────────────────────────────────
def get_next_unused_key():
    keys = fetch_json("keys.json")
    for k in keys:
        if not k.startswith("-"):
            return k
    return None                    # none left

def build_df(raw):
    rows = []
    for g in raw:
        status = "setup" if g.get("channel") and g.get("role") else "activated"
        rows.append({
            "guild_id": str(g.get("id", "")),
            "channel":  str(g.get("channel", "")),
            "role":     str(g.get("role", "")),
            "status":   status
        })
    return pd.DataFrame(rows)

def df_test_guilds():
    return build_df(fetch_json("test_guilds.json"))

def df_guilds():
    return build_df(fetch_json("guilds.json"))

def revoke_guild(guild_id: str):
    guilds = fetch_json("guilds.json")
    new_guilds = [g for g in guilds if str(g.get("id")) != guild_id]
    if len(new_guilds) == len(guilds):
        return False                 # nothing removed
    upload_json("guilds.json", new_guilds)
    return True

# ───────────────────────────────────────────────
# Streamlit UI
# ───────────────────────────────────────────────
st.title("ACM Guild Admin Panel")

# Buttons row
col1, col2, col3 = st.columns(3)

# Full-width container for tables
table_container = st.container()

# --- Grab key ---
with col1:
    if st.button("🔑 Next Unused Key"):
        key = get_next_unused_key()
        if key == "No Keys Left!":
            st.error(key)
        else:
            st.success(f"Next unused activation key:\n{key}")
# --- Show test guilds ---
with col2:
    if st.button("🧪 Show Test Guilds"):
        df = df_test_guilds()
        if df.empty:
            st.warning("No test guilds found.")
        else:
            with table_container:
                st.dataframe(df, use_container_width=True)

# --- Show prod guilds ---
with col3:
    if st.button("📜 Show Guild Statuses"):
        df = df_guilds()
        if df.empty:
            st.warning("No guilds found.")
        else:
            with table_container:
                st.dataframe(df, use_container_width=True)

# Revoke section (also full-width by default)
st.divider()
st.subheader("🔒 Revoke Guild Access (delete entry)")

gid = st.text_input("Guild ID", placeholder="123456789012345678")
if st.button("Revoke"):
    if not gid:
        st.warning("Enter a guild ID first")
    elif revoke_guild(gid.strip()):
        st.success(f"Guild {gid} removed from guilds.json")
    else:
        st.error("Guild ID not found")
