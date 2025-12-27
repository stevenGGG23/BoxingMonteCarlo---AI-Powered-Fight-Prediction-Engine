#!/usr/bin/env python
"""
Test the RapidAPI boxing-data-api to understand available endpoints
"""

import requests
import json

# RapidAPI credentials
RAPIDAPI_HOST = "boxing-data-api.p.rapidapi.com"
RAPIDAPI_KEY = "954b586842msha9c5947f76e426bp13b543jsnd28cc99ca940"

headers = {
    "x-rapidapi-host": RAPIDAPI_HOST,
    "x-rapidapi-key": RAPIDAPI_KEY
}

print("="*80)
print("EXPLORING BOXING-DATA-API ENDPOINTS")
print("="*80)

# Test 1: Try events endpoint
print("\n1. Testing /v1/events/schedule endpoint...")
url = "https://boxing-data-api.p.rapidapi.com/v1/events/schedule"
params = {
    "days": 7,
    "past_hours": 12,
    "date_sort": "ASC",
    "page_num": 1,
    "page_size": 5
}

try:
    response = requests.get(url, headers=headers, params=params, timeout=10)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response keys: {list(data.keys())}")
    if data.get('data'):
        print(f"First event: {json.dumps(data['data'][0], indent=2)[:500]}...")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Try searching for a fighter
print("\n2. Testing fighter search endpoints...")
possible_endpoints = [
    "/v1/fighters/search",
    "/v1/fighters",
    "/v1/search",
]

for endpoint in possible_endpoints:
    url = f"https://boxing-data-api.p.rapidapi.com{endpoint}"
    print(f"\n  Trying {endpoint}...")
    try:
        response = requests.get(url, headers=headers, params={"q": "Crawford"}, timeout=10)
        print(f"    Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"    Response keys: {list(data.keys())}")
            print(f"    Data: {json.dumps(data, indent=2)[:300]}...")
    except Exception as e:
        print(f"    Error: {e}")

print("\n" + "="*80)
