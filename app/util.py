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

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET = os.getenv("AWS_SECRET")

s3 = boto3.client("s3",region_name = "us-east-2", aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET)
bucket_name = "acm-github-data"


def getDataFromJSON(filename):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=filename)
        data = response['Body'].read().decode('utf-8')
        return json.loads(data)
    except Exception as e:
        print(f"Error retrieving {filename} from S3: {e}")
        return None 

def saveDataToJSON(filename, data, pretty=False):
    s3.put_object(Body=json.dumps(data, indent=(4 if pretty else 0)), Bucket=bucket_name, Key=filename)

def isValidActivationKey(key):
    # Get activation keys from S3
    activation_keys = getDataFromJSON("keys.json")
    
    # Check if key exists in list of activation keys
    idx = -1
    for i, activation_key in enumerate(activation_keys):
        # Skip keys that have already been used
        if activation_key.startswith("-"):
            pass
        
        # Found matching activation key
        if activation_key == key:
            idx = i
            break
    if idx == -1:
        return False

    activation_keys[idx] = "-" + activation_keys[idx]
    saveDataToJSON("keys.json", activation_keys, True)
    return True


def sortListings(listings):
    oldestListingFromCompany = {}
    linkForCompany = {}

    for listing in listings:
        date_posted = listing["date_posted"]
        if listing["company_name"].lower() not in oldestListingFromCompany or oldestListingFromCompany[listing["company_name"].lower()] > date_posted:
            oldestListingFromCompany[listing["company_name"].lower(
            )] = date_posted
        if listing["company_name"] not in linkForCompany or len(listing["company_url"]) > 0:
            linkForCompany[listing["company_name"]] = listing["company_url"]

    listings.sort(
        key=lambda x: (
            x["active"],  # Active listings first
            datetime(
                datetime.fromtimestamp(x["date_posted"]).year,
                datetime.fromtimestamp(x["date_posted"]).month,
                datetime.fromtimestamp(x["date_posted"]).day
            ),
            x['company_name'].lower(),
            x['date_updated']
        ),
        reverse=True
    )

    for listing in listings:
        listing["company_url"] = linkForCompany[listing["company_name"]]

    return listings


#def filterSummer(listings, year, earliest_date):
    #return [listing for listing in listings if listing["is_visible"] and any(f"Summer {year}" in item for item in listing["terms"]) and listing['date_posted'] > earliest_date]


def filterSummer(listings, year, earliest_date=0):
    filtered = []
    for listing in listings:
        # Check if date_posted is after earliest_date
        date_posted = int(listing["date_posted"])
        if date_posted >= earliest_date:
            # Check if any term contains the specified year
            if any(year in term for term in listing["terms"]):
                filtered.append(listing)

 
    return filtered
