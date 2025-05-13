# guild_admin_ui.py  –  Streamlit dashboard for ACM-Connect
# --------------------------------------------------------

# ── imports & page config (FIRST Streamlit call) ─────────────────────────
import streamlit as st
st.set_page_config(page_title="ACM Connect Admin Dashboard",
                   page_icon="🛠️",
                   layout="centered")

import os, json, boto3, pandas as pd, secrets
from dotenv import load_dotenv

# ── AWS / S3 helpers ─────────────────────────────────────────────────────
load_dotenv()
REGION, BUCKET = "us-east-2", "acm-github-data"

s3 = boto3.client(
    "s3",
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET"),
)

def fetch_json(key: str):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode())
    except Exception as exc:
        st.error(f"Error fetching {key}: {exc}")
        return []

def upload_json(key: str, data):
    s3.put_object(Bucket=BUCKET,
                  Key=key,
                  Body=json.dumps(data, indent=4).encode())

# ── dataframe helper (id, name first) ────────────────────────────────────

def to_df(records):
    """Cast all values to str; order columns: id, name, everything else."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame([{k: str(v) for k, v in r.items()} for r in records])
    first = [c for c in ("id", "name") if c in df.columns]
    rest  = sorted(c for c in df.columns if c not in first)
    return df[first + rest]

# quick accessors
def df_test(): return to_df(fetch_json("test_guilds.json"))
def df_prod(): return to_df(fetch_json("guilds.json"))

# ── revoke helpers (hard delete) ─────────────────────────────────────────

def revoke_entry(guild_id: str, filename: str) -> bool:
    """Delete entry from <filename>; return True if removed."""
    rows = fetch_json(filename)
    new_rows = [g for g in rows if str(g.get("id")) != guild_id]
    if len(new_rows) == len(rows):
        return False
    upload_json(filename, new_rows)
    return True

# activation‑key helper stays unchanged

def get_next_unused_key():
    for k in fetch_json("keys.json"):
        if not k.startswith("-"):
            return k
    return "No Keys Left!"

# ── key‑management helpers ───────────────────────────────────────────────

def fetch_keys():
    return fetch_json("keys.json")


def save_keys(keys):
    upload_json("keys.json", keys)


def key_counts(keys):
    used = sum(1 for k in keys if k.startswith("-"))
    unused = len(keys) - used
    return used, unused


def add_new_keys(n: int):
    """Generate <n> unique 32‑char hex keys and append to keys.json."""
    keys = fetch_keys()
    existing = set(k.lstrip("-") for k in keys)  # strip dashes for uniqueness
    added = []
    while len(added) < n:
        k = secrets.token_hex(16)
        if k not in existing:
            added.append(k)
            existing.add(k)
    keys.extend(added)
    save_keys(keys)
    return added

# ── Streamlit UI ─────────────────────────────────────────────────────────
st.title("ACM Guild Admin Panel")

col1, col2, col3 = st.columns(3)
table_area = st.container()    # full-width slot for any table

# 1️⃣  next unused key -----------------------------------------------------
with col1:
    if st.button("🔑 Next Unused Key"):
        key = get_next_unused_key()
        if key == "No Keys Left!":
            st.error(key)
        else:
            st.success(key)

# 2️⃣  show test guilds ----------------------------------------------------
with col2:
    if st.button("🧪 Show Test Guilds"):
        df = df_test()
        with table_area:
            if df.empty:
                st.warning("No test guilds.")
            else:
                st.dataframe(df, use_container_width=True)

# 3️⃣  show production guilds ---------------------------------------------
with col3:
    if st.button("📜 Show Guilds"):
        df = df_prod()
        with table_area:
            if df.empty:
                st.warning("No guilds found.")
            else:
                st.dataframe(df, use_container_width=True)

# 4️⃣  revoke (hard delete) -----------------------------------------------
st.divider()
left, right = st.columns(2)

# -- production revoke --
with left:
    st.subheader("🔒 Revoke PROD Guild")
    gid_prod = st.text_input("Prod Guild ID", key="revoke_prod")
    if st.button("Revoke Prod"):
        if not gid_prod:
            st.warning("Enter a guild ID.")
        elif revoke_entry(gid_prod.strip(), "guilds.json"):
            st.success(f"Prod guild {gid_prod} deleted.")
        else:
            st.error("Guild ID not found in prod list.")

# -- test revoke --
with right:
    st.subheader("🧪 Revoke TEST Guild")
    gid_test = st.text_input("Test Guild ID", key="revoke_test")
    if st.button("Revoke Test"):
        if not gid_test:
            st.warning("Enter a guild ID.")
        elif revoke_entry(gid_test.strip(), "test_guilds.json"):
            st.success(f"Test guild {gid_test} deleted.")
        else:
            st.error("Guild ID not found in test list.")

# ── key management UI -----------------------------------------------------
st.divider()
st.header("🔑 Key Management")

all_keys = fetch_keys()
used_ct, unused_ct = key_counts(all_keys)

# Display counts like a dashboard metric
st.markdown(
    f"**Keys in circulation (unused):** {unused_ct} of {len(all_keys)} — **Used:** {used_ct}")

km_col1, km_col2 = st.columns(2)

# -- generate new keys --
with km_col1:
    st.subheader("➕ Add New Keys")
    num_new = st.number_input("Number of keys to generate", min_value=1, max_value=100, value=1, step=1)
    if st.button("Add Keys"):
        added = add_new_keys(int(num_new))
        st.success(f"Added {len(added)} new keys.")

# -- fetch next key (duplicate of original but placed here for convenience) --
with km_col2:
    st.subheader("➡️ Get Next Unused Key")
    if st.button("Fetch Next Key"):
        next_key = get_next_unused_key()
        if next_key == "No Keys Left!":
            st.error(next_key)
        else:
            st.success(next_key)

