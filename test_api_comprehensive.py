#!/usr/bin/env python
"""
Comprehensive API test with multiple boxers and matchups
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import create_app
import json

# Create the Flask app
app = create_app()

# Test cases with different fighters
test_cases = [
    ('Tyson Fury', 'Canelo Alvarez', 'Heavyweight vs Super Middleweight'),
    ('Floyd Mayweather', 'Manny Pacquiao', 'Welterweight classics'),
    ('Mike Tyson', 'Evander Holyfield', 'Heavyweight legends'),
    ('Jake Paul', 'Canelo Alvarez', 'Internet celebrity vs Pro'),
    ('Terence Crawford', 'Floyd Mayweather', 'Modern vs Historic greatness'),
]

print("="*80)
print("COMPREHENSIVE API TEST - MULTIPLE BOXERS")
print("="*80)

with app.test_client() as client:
    for i, (f1, f2, description) in enumerate(test_cases, 1):
        print(f"\n{i}. {f1.upper()} vs {f2.upper()}")
        print(f"   ({description})")
        print("-" * 80)
        
        response = client.post('/api/simulate', 
            json={
                'fighter1': f1, 
                'fighter2': f2, 
                'n_simulations': 50000
            })
        
        data = json.loads(response.data)
        
        if response.status_code == 404:
            print(f"   ❌ ERROR: {data.get('error')}")
            print(f"   Suggestion: {data.get('suggestion')}")
        elif response.status_code == 200:
            results = data.get('results', {})
            warnings = data.get('warnings', [])
            f1_data = data.get('fighter1', {})
            f2_data = data.get('fighter2', {})
            
            print(f"   ✅ SUCCESS")
            print(f"   Fighter 1: {f1_data.get('name')} - {f1_data.get('wins')}-{f1_data.get('losses')}-{f1_data.get('draws')} ({f1_data.get('weight')} lbs)")
            print(f"   Fighter 2: {f2_data.get('name')} - {f2_data.get('wins')}-{f2_data.get('losses')}-{f2_data.get('draws')} ({f2_data.get('weight')} lbs)")
            print(f"\n   Results ({results.get('fighter1_wins', 0) + results.get('fighter2_wins', 0) + results.get('draws', 0):,} simulations):")
            print(f"   {f1_data.get('name')}: {results.get('fighter1_win_pct', 0):.1f}%")
            print(f"   {f2_data.get('name')}: {results.get('fighter2_win_pct', 0):.1f}%")
            print(f"   Draws: {results.get('draw_pct', 0):.1f}%")
            
            if warnings:
                print(f"\n   ⚠️  WARNINGS:")
                for warning in warnings:
                    print(f"   {warning}")
        else:
            print(f"   ❌ Unexpected status code: {response.status_code}")
            print(f"   Response: {data}")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
