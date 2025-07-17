# guild_admin_ui.py  –  Streamlit dashboard for ACM-Connect
# --------------------------------------------------------

# ── imports & page config (FIRST Streamlit call) ─────────────────────────
import streamlit as st
st.set_page_config(page_title="ACM Connect Admin Dashboard",
                   page_icon="🛠️",
                   layout="centered")

import os, json, boto3, pandas as pd, secrets, sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add app directory to path to import utilities
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))

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

# ── listings debugging UI ────────────────────────────────────────────────
st.divider()
st.header("🐛 Listings Debug")

def get_daily_listings_debug():
    """Fetch and filter listings using smart upcoming term detection."""
    try:
        # Fetch raw listings directly from S3
        listings = fetch_json("listings.json")
        if not listings:
            return None, "Failed to fetch listings.json from S3"
        
        # Calculate yesterday's 9 PM UTC (2 AM UTC) as earliest_date
        today = datetime.now()
        previous_day = today - timedelta(days=1)
        nine_pm_previous_day = datetime(previous_day.year, previous_day.month, previous_day.day, 2, 0, 0)
        earliest_date = int(nine_pm_previous_day.timestamp())
        
        # Smart term detection - determine current term and upcoming terms
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        if 1 <= current_month <= 5:  # January to May = Spring
            current_term = "Spring"
        elif 6 <= current_month <= 7:  # June to July = Summer  
            current_term = "Summer"
        elif 8 <= current_month <= 12:  # August to December = Fall
            current_term = "Fall"
        
        # Define upcoming terms to look for (proper year rollover)
        upcoming_terms = []
        if current_term == "Spring":
            upcoming_terms = [f"Summer {current_year}", f"Fall {current_year}", f"Winter {current_year}", f"Spring {current_year + 1}"]
        elif current_term == "Summer":
            upcoming_terms = [f"Fall {current_year}", f"Winter {current_year}", f"Spring {current_year + 1}", f"Summer {current_year + 1}"]
        elif current_term == "Fall":
            upcoming_terms = [f"Winter {current_year}", f"Spring {current_year + 1}", f"Summer {current_year + 1}", f"Fall {current_year + 1}"]
        
        # Filtering with detailed analysis
        filtered_listings = []
        filter_stats = {
            "total": len(listings),
            "current_term": f"{current_term} {current_year}",
            "upcoming_terms": upcoming_terms,
            "has_upcoming_terms": 0,
            "posted_after_earliest": 0,
            "both_conditions": 0,
            "date_too_old": 0,
            "no_upcoming_terms": 0,
            "none_type_errors": 0,
            "other_errors": 0
        }
        
        term_analysis = {}
        errors = []
        none_type_errors = []
        
        for i, listing in enumerate(listings):
            try:
                # Basic validation
                if listing is None:
                    none_type_errors.append(f"Listing at index {i} is None")
                    filter_stats["none_type_errors"] += 1
                    continue
                
                if not isinstance(listing, dict):
                    errors.append(f"Listing at index {i} is not a dict: {type(listing)}")
                    filter_stats["other_errors"] += 1
                    continue
                
                # Check date_posted
                date_posted = listing.get("date_posted")
                if date_posted is None:
                    none_type_errors.append(f"Listing {i}: date_posted is None")
                    filter_stats["none_type_errors"] += 1
                    continue
                
                try:
                    date_posted = int(date_posted)
                except (ValueError, TypeError):
                    errors.append(f"Listing {i}: Invalid date_posted: {date_posted}")
                    filter_stats["other_errors"] += 1
                    continue
                
                # Count date filtering
                if date_posted >= earliest_date:
                    filter_stats["posted_after_earliest"] += 1
                else:
                    filter_stats["date_too_old"] += 1
                
                # Check terms field
                terms = listing.get("terms")
                if terms is None:
                    none_type_errors.append(f"Listing {i}: terms is None")
                    filter_stats["none_type_errors"] += 1
                    continue
                
                if not isinstance(terms, list):
                    errors.append(f"Listing {i}: terms is not a list: {type(terms)}")
                    filter_stats["other_errors"] += 1
                    continue
                
                # Analyze terms and check for upcoming terms
                has_upcoming_term = False
                for term in terms:
                    if term is None:
                        none_type_errors.append(f"Listing {i}: term in terms is None")
                        continue
                    
                    term_str = str(term).strip()
                    if term_str not in term_analysis:
                        term_analysis[term_str] = 0
                    term_analysis[term_str] += 1
                    
                    # Check if this term matches any upcoming term
                    for upcoming_term in upcoming_terms:
                        if upcoming_term.lower() in term_str.lower():
                            has_upcoming_term = True
                            break
                    if has_upcoming_term:
                        break
                
                if has_upcoming_term:
                    filter_stats["has_upcoming_terms"] += 1
                    # Apply both filters (date + upcoming terms)
                    if date_posted >= earliest_date:
                        filter_stats["both_conditions"] += 1
                        filtered_listings.append(listing)
                else:
                    filter_stats["no_upcoming_terms"] += 1
                    
            except Exception as e:
                errors.append(f"Listing {i}: Unexpected error: {str(e)}")
                filter_stats["other_errors"] += 1
        
        debug_info = {
            "filter_stats": filter_stats,
            "term_analysis": dict(sorted(term_analysis.items(), key=lambda x: x[1], reverse=True)),
            "earliest_date_readable": nine_pm_previous_day.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "errors": errors,
            "none_type_errors": none_type_errors,
            "filtered_listings": len(filtered_listings)
        }
        
        return filtered_listings, debug_info
        
    except Exception as e:
        return None, f"Critical error processing listings: {str(e)}"

if st.button("🔍 Show Today's Listings Debug"):
    with st.spinner("Fetching and processing listings..."):
        listings, debug_info = get_daily_listings_debug()
        
        if listings is None:
            st.error(debug_info)
        else:
            # Show debug information
            st.subheader("📊 Smart Term Filtering Debug")
            
            # Current term info
            st.info(f"**Current Term:** {debug_info['filter_stats']['current_term']}")
            st.info(f"**Looking for upcoming terms:** {', '.join(debug_info['filter_stats']['upcoming_terms'])}")
            st.info(f"**Date Filter:** Listings posted after {debug_info['earliest_date_readable']}")
            
            # Metrics
            col_debug1, col_debug2, col_debug3, col_debug4 = st.columns(4)
            
            with col_debug1:
                st.metric("Total Listings", debug_info["filter_stats"]["total"])
            with col_debug2:
                st.metric("Final Filtered", debug_info["filtered_listings"])
            with col_debug3:
                st.metric("Has Upcoming Terms", debug_info["filter_stats"]["has_upcoming_terms"])
            with col_debug4:
                st.metric("Recent Enough", debug_info["filter_stats"]["posted_after_earliest"])
            
            # Filter breakdown
            st.subheader("🔍 Filter Breakdown")
            breakdown_col1, breakdown_col2 = st.columns(2)
            
            with breakdown_col1:
                st.metric("✅ Both Conditions Met", debug_info["filter_stats"]["both_conditions"])
                st.metric("📅 Date Too Old", debug_info["filter_stats"]["date_too_old"])
            
            with breakdown_col2:
                st.metric("❌ No Upcoming Terms", debug_info["filter_stats"]["no_upcoming_terms"])
                st.metric("🚨 Data Errors", debug_info["filter_stats"]["none_type_errors"] + debug_info["filter_stats"]["other_errors"])
            
            # Show term analysis
            if debug_info["term_analysis"]:
                st.subheader("📋 Term Analysis (Top 10)")
                term_items = list(debug_info["term_analysis"].items())[:10]
                term_df = pd.DataFrame(term_items, columns=["Term", "Count"])
                st.dataframe(term_df, use_container_width=True)
            
            # Show errors if they exist
            if debug_info["filter_stats"]["none_type_errors"] > 0:
                st.error(f"🚨 Found {debug_info['filter_stats']['none_type_errors']} NoneType errors - this is likely causing your bot crashes!")
                with st.expander("🔍 View NoneType Errors"):
                    for error in debug_info["none_type_errors"]:
                        st.text(error)
            
            if debug_info["filter_stats"]["other_errors"] > 0:
                st.warning(f"⚠️ Found {debug_info['filter_stats']['other_errors']} other data issues")
                with st.expander("🔍 View Other Errors"):
                    for error in debug_info["errors"]:
                        st.text(error)
            
            # Show listings table
            if listings:
                st.subheader(f"📋 Filtered Listings ({len(listings)} items)")
                
                # Convert to DataFrame for better display
                listings_df = []
                for listing in listings:
                    listings_df.append({
                        "Company": listing.get("company_name", "N/A"),
                        "Title": listing.get("title", "N/A"),
                        "Locations": ", ".join(listing.get("locations", [])),
                        "Terms": ", ".join(listing.get("terms", [])),
                        "Sponsorship": listing.get("sponsorship", "N/A"),
                        "Posted": datetime.fromtimestamp(listing.get("date_posted", 0)).strftime("%m/%d/%Y %H:%M"),
                        "Updated": datetime.fromtimestamp(listing.get("date_updated", 0)).strftime("%m/%d/%Y %H:%M"),
                        "Active": listing.get("active", False),
                        "URL": listing.get("url", "N/A")
                    })
                
                df = pd.DataFrame(listings_df)
                st.dataframe(df, use_container_width=True)
                
                # Show raw JSON for filtered listings (what the bot actually processes)
                with st.expander(f"🔧 Raw JSON - Filtered Listings (Bot Input) - Showing {min(len(listings), 5)} of {len(listings)}"):
                    st.info("This is the exact JSON data that your bot receives after smart term filtering")
                    st.json(listings[:5])  # Show first 5 filtered listings instead of 3
            else:
                st.warning("No listings match the current filter criteria.")

