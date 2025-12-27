#!/usr/bin/env python
"""
Test script to simulate Crawford vs Joshua with updated logic
"""

import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import monte_carlo_simulation

# Crawford stats: Welterweight champion, mostly defensive boxer
crawford_stats = {
    'name': 'Terence Crawford',
    'wins': 42,
    'losses': 0,
    'draws': 0,
    'total_bouts': 42,
    'ko_wins': 31,
    'height': 178,
    'reach': 183,
    'weight': 147
}

# Joshua stats: Heavyweight, power puncher
joshua_stats = {
    'name': 'Anthony Joshua',
    'wins': 28,
    'losses': 3,
    'draws': 0,
    'total_bouts': 31,
    'ko_wins': 25,
    'height': 198,
    'reach': 208,
    'weight': 240
}

print("\n" + "="*70)
print("TESTING UPDATED SIMULATION: CRAWFORD vs JOSHUA")
print("="*70)
print("\nKey improvements:")
print("✓ KO Rate: NOW ko_wins / total_bouts (was ko_wins / wins)")
print("✓ Weight Class: Added 15% weight advantage weighting")
print("✓ Weight Diff: Crawford 147 lbs vs Joshua 240 lbs = 93 lbs advantage")
print("="*70)

# Create DataFrames
f1_df = pd.DataFrame([crawford_stats])
f2_df = pd.DataFrame([joshua_stats])

# Run simulation with 100,000 simulations
n_simulations = 100_000
results = monte_carlo_simulation(f1_df, f2_df, n_simulations=n_simulations, use_multiprocessing=True)

# Print results
print(f"\n{'='*70}")
print("SIMULATION RESULTS")
print(f"{'='*70}")
print(f"Total Simulations: {n_simulations:,}")
print(f"\nOutcomes:")
print(f"  Terence Crawford Wins: {results['fighter1_wins']:,} ({results['fighter1_win_pct']:.2f}%)")
print(f"  Anthony Joshua Wins:   {results['fighter2_wins']:,} ({results['fighter2_win_pct']:.2f}%)")
print(f"  Draws:                 {results['draws']:,} ({results['draw_pct']:.2f}%)")
print(f"\nExecution Time: {results['execution_time']:.2f} seconds")
print(f"Throughput: {results['throughput']:,.0f} simulations/second")

# Verify weight class impact
if results['fighter2_win_pct'] > 80:
    print(f"\n✅ Weight class advantage working! Joshua {results['fighter2_win_pct']:.1f}% > expected ~80%")
else:
    print(f"\n⚠ Joshua win rate {results['fighter2_win_pct']:.1f}% - weight class may need adjustment")

print(f"{'='*70}\n")
