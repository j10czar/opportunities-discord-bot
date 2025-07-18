"""
See
    https://github.com/SimplifyJobs/Summer2025-Internships/blob/dev/.github/README-scripts.md
    Based on https://github.com/SimplifyJobs/Summer2025-Internships/blob/dev/.github/scripts/util.py
"""

from datetime import datetime

import os
from dotenv import load_dotenv
load_dotenv()

import boto3
import json

# ──────────────────────────────────────────────────────────────────────────
# AWS credentials + client
#   Expect AWS_ACCESS_KEY / AWS_SECRET in environment
# ──────────────────────────────────────────────────────────────────────────
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET = os.getenv("AWS_SECRET")

s3 = boto3.client(
    "s3",
    region_name="us-east-2",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET,
)
bucket_name = "acm-github-data"

# ──────────────────────────────────────────────────────────────────────────
# S3 JSON convenience wrappers
# ──────────────────────────────────────────────────────────────────────────
def getDataFromJSON(filename):
    """Fetch JSON file from S3 and return parsed object (or None on error)."""
    try:
        response = s3.get_object(Bucket=bucket_name, Key=filename)
        data = response["Body"].read().decode("utf-8")
        return json.loads(data)
    except Exception as e:
        print(f"Error retrieving {filename} from S3: {e}")
        return None


def saveDataToJSON(filename, data, pretty=False):
    """Upload Python object to S3 as JSON (optionally pretty-printed)."""
    s3.put_object(
        Body=json.dumps(data, indent=(4 if pretty else 0)),
        Bucket=bucket_name,
        Key=filename,
    )

# ──────────────────────────────────────────────────────────────────────────
# One-time activation key validator
#   • Keys live in keys.json
#   • “Burns” a key by prefixing it with ‘-’
# ──────────────────────────────────────────────────────────────────────────
def isValidActivationKey(key):
    activation_keys = getDataFromJSON("keys.json")

    idx = -1
    for i, activation_key in enumerate(activation_keys):
        if activation_key.startswith("-"):         # already used
            continue
        if activation_key == key:                  # match
            idx = i
            break

    if idx == -1:                                 # not found
        return False

    activation_keys[idx] = "-" + activation_keys[idx]  # burn key
    saveDataToJSON("keys.json", activation_keys, True)
    return True

# ──────────────────────────────────────────────────────────────────────────
# Listing utilities: sort + filters
# ──────────────────────────────────────────────────────────────────────────
def sortListings(listings):
    """
    Sort order:
      1. Active listings first
      2. Newest posting date
      3. Company name A-Z
      4. Most-recently updated
    Also normalises company_url per company.
    """
    oldestListingFromCompany = {}
    linkForCompany = {}

    for listing in listings:
        date_posted = listing["date_posted"]
        name_lc = listing["company_name"].lower()

        # Track oldest post date per company
        if (name_lc not in oldestListingFromCompany or
                oldestListingFromCompany[name_lc] > date_posted):
            oldestListingFromCompany[name_lc] = date_posted

        # Canonical link per company
        if (listing["company_name"] not in linkForCompany or
                len(listing["company_url"]) > 0):
            linkForCompany[listing["company_name"]] = listing["company_url"]

    listings.sort(
        key=lambda x: (
            x["active"],
            datetime(
                datetime.fromtimestamp(x["date_posted"]).year,
                datetime.fromtimestamp(x["date_posted"]).month,
                datetime.fromtimestamp(x["date_posted"]).day,
            ),
            x["company_name"].lower(),
            x["date_updated"],
        ),
        reverse=True,
    )

    # Patch company_url post-sort
    for listing in listings:
        listing["company_url"] = linkForCompany[listing["company_name"]]

    return listings

def filterByTime(listings, year=None, earliest_date=0):
    """
    Filter listings to only include those posted within the specified time period.
    
    This function performs date-only filtering based on the earliest_date parameter.
    It uses a simple 24-hour lookback approach to include all recent listings.
    
    Term-based filtering has been completely removed for simplicity and to ensure
    that all relevant internship opportunities are included regardless of their
    term content. Previously, listings were filtered by terms containing a specific
    year, but this approach was too restrictive and caused valid listings to be
    excluded.
    
    Args:
        listings: List of listing dictionaries to filter
        year: Unused parameter kept for backward compatibility (ignored)
        earliest_date: Unix timestamp - only listings posted after this time are included
    
    Returns:
        List of listings with date_posted >= earliest_date
    """
    filtered = []
    for listing in listings:
        try:
            # Only filter by date - no term checking
            if int(listing["date_posted"]) >= earliest_date:
                filtered.append(listing)
        except (ValueError, TypeError, KeyError):
            # Skip listings with invalid date_posted values
            continue
    return filtered


def filterSummer(listings, year, earliest_date=0):
    """
    Deprecated: Use filterByTime instead. 
    
    This function is kept for backward compatibility during transition.
    It now delegates to filterByTime and ignores term-based filtering.
    """
    return filterByTime(listings, year, earliest_date)

# ──────────────────────────────────────────────────────────────────────────
# Discord helper: make guild/role/channel names human-readable for logs
# ──────────────────────────────────────────────────────────────────────────
def get_guild_info(guild_data, bot):
    """
    Resolve {id, role, channel} ints into display-names.
    Returns dict ready for pretty logging/debugging.
    """
    guild_info = {
        "guild": guild_data["id"],
        "role": "role-not-configured",
        "channel": "channel-not-configured",
    }

    discord_guild = bot.get_guild(guild_data["id"])
    if discord_guild:
        guild_info["guild"] = discord_guild.name

        if "role" in guild_data:
            discord_role = discord_guild.get_role(guild_data["role"])
            guild_info["role"] = discord_role.name if discord_role else "role-deleted"

        if "channel" in guild_data:
            discord_channel = bot.get_channel(guild_data["channel"])
            guild_info["channel"] = (
                discord_channel.name if discord_channel else "channel-deleted"
            )

    return guild_info

