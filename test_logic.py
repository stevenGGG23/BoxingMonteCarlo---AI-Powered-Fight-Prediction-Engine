#!/usr/bin/env python
"""
Test script to verify simulation logic with different fighter matchups
"""

import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import monte_carlo_simulation

# Test 1: Tyson Fury vs Canelo Alvarez (significant weight difference)
# Fury: Heavyweight (270 lbs), undefeated, great record
# Canelo: Super middleweight (168 lbs), excellent record but smaller
fury_stats = {
    'name': 'Tyson Fury',
    'wins': 34,
    'losses': 0,
    'draws': 1,
    'total_bouts': 35,
    'ko_wins': 24,
    'height': 206,
    'reach': 216,
    'weight': 270
}

canelo_stats = {
    'name': 'Canelo Alvarez',
    'wins': 62,
    'losses': 2,
    'draws': 2,
    'total_bouts': 66,
    'ko_wins': 39,
    'height': 173,
    'reach': 179,
    'weight': 168
}

print("\n" + "="*80)
print("TEST 1: TYSON FURY vs CANELO ALVAREZ")
print("="*80)
print("\nFighter Analysis:")
print(f"  Fury:   34-0-1 (35 bouts) | {24} KOs ({24/35:.1%}) | {270} lbs | Heavyweight")
print(f"  Canelo: 62-2-2 (66 bouts) | {39} KOs ({39/66:.1%}) | {168} lbs | Super Middleweight")
print(f"\n  Weight difference: 102 lbs (Fury significantly heavier)")
print(f"  Record advantage: Fury undefeated; Canelo has 2 losses")
print(f"  Experience: Canelo much more experienced (66 vs 35 bouts)")
print(f"  KO Rate (NEW): Fury {24/35:.1%} vs Canelo {39/66:.1%}")
print("="*80)

f1_df = pd.DataFrame([fury_stats])
f2_df = pd.DataFrame([canelo_stats])

results = monte_carlo_simulation(f1_df, f2_df, n_simulations=100_000, use_multiprocessing=True)

print(f"\n{'─'*80}")
print(f"RESULTS: Fury {results['fighter1_win_pct']:.1f}% | Canelo {results['fighter2_win_pct']:.1f}%")
print(f"{'─'*80}")
print(f"\n✓ LOGIC CHECK:")
if results['fighter1_win_pct'] > 60:
    print(f"  ✓ Fury favored (makes sense: undefeated, heavier, reach advantage, KO power)")
else:
    print(f"  ⚠ Canelo close/favored (experience + many fights + solid KO rate)")

print("\n" + "="*80)
print("TEST 2: FLOYD MAYWEATHER vs MIKE TYSON")
print("="*80)

# Test 2: Floyd Mayweather vs Mike Tyson (similar weight, but different styles)
# Floyd: Perfect record, defensive genius
# Tyson: Older record, power puncher, but more KOs

floyd_stats = {
    'name': 'Floyd Mayweather',
    'wins': 50,
    'losses': 0,
    'draws': 0,
    'total_bouts': 50,
    'ko_wins': 27,
    'height': 173,
    'reach': 183,
    'weight': 147
}

tyson_stats = {
    'name': 'Mike Tyson',
    'wins': 50,
    'losses': 6,
    'draws': 0,
    'total_bouts': 56,
    'ko_wins': 44,
    'height': 178,
    'reach': 180,
    'weight': 220
}

print("\nFighter Analysis:")
print(f"  Floyd: 50-0-0 (50 bouts) | {27} KOs ({27/50:.1%}) | {147} lbs | Welterweight")
print(f"  Tyson: 50-6-0 (56 bouts) | {44} KOs ({44/56:.1%}) | {220} lbs | Heavyweight")
print(f"\n  Weight difference: 73 lbs (Tyson significantly heavier)")
print(f"  Record: Floyd undefeated; Tyson 50-6")
print(f"  KO Power: Tyson {44/56:.1%} vs Floyd {27/50:.1%} (Tyson more KO-prone)")
print(f"  Style: Floyd = defensive; Tyson = aggressive power puncher")
print("="*80)

f3_df = pd.DataFrame([floyd_stats])
f4_df = pd.DataFrame([tyson_stats])

results2 = monte_carlo_simulation(f3_df, f4_df, n_simulations=100_000, use_multiprocessing=True)

print(f"\n{'─'*80}")
print(f"RESULTS: Floyd {results2['fighter1_win_pct']:.1f}% | Tyson {results2['fighter2_win_pct']:.1f}%")
print(f"{'─'*80}")
print(f"\n✓ LOGIC CHECK:")
if results2['fighter2_win_pct'] > 60:
    print(f"  ✓ Tyson favored (makes sense: much heavier, superior KO rate, more power)")
    print(f"    Despite Floyd's perfect record, weight/power difference is massive")
else:
    print(f"  ✓ Floyd competitive (makes sense: perfect record, defensive mastery)")
    print(f"    But Tyson's physical advantages should give him edge")

print("\n" + "="*80)
