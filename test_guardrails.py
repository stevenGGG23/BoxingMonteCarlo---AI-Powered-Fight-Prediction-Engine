#!/usr/bin/env python
"""
Test user data guardrails - test spelling errors and missing fighters
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import create_app
import json

# Create the Flask app
app = create_app()

# Test with Flask test client
with app.test_client() as client:
    print("="*80)
    print("TEST 1: Valid fighters (Crawford vs Joshua)")
    print("="*80)
    response = client.post('/api/simulate', 
        json={'fighter1': 'Terence Crawford', 'fighter2': 'Anthony Joshua', 'n_simulations': 10000})
    data = json.loads(response.data)
    print(f"Status: {response.status_code}")
    print(f"Warnings: {data.get('warnings', [])}")
    if 'error' in data:
        print(f"Error: {data['error']}")
    print()
    
    print("="*80)
    print("TEST 2: Misspelled fighter (Anthonny Joshua - typo)")
    print("="*80)
    response = client.post('/api/simulate', 
        json={'fighter1': 'Terence Crawford', 'fighter2': 'Anthonny Joshua', 'n_simulations': 10000})
    data = json.loads(response.data)
    print(f"Status: {response.status_code}")
    print(f"Error: {data.get('error', 'No error')}")
    print(f"Suggestion: {data.get('suggestion', 'No suggestion')}")
    print(f"Available fighters: {data.get('available_fighters', [])[:3]}... (showing first 3)")
    print()
    
    print("="*80)
    print("TEST 3: Unknown fighter (Fake Fighter)")
    print("="*80)
    response = client.post('/api/simulate', 
        json={'fighter1': 'Terence Crawford', 'fighter2': 'Fake Fighter', 'n_simulations': 10000})
    data = json.loads(response.data)
    print(f"Status: {response.status_code}")
    print(f"Error: {data.get('error', 'No error')}")
    print(f"Suggestion: {data.get('suggestion', 'No suggestion')}")
    print()
