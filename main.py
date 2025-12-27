import requests
import numpy as np
import pandas as pd
import os
import time
from multiprocessing import Pool, cpu_count
from flask import Flask, render_template, request, jsonify

# Optional: keep matplotlib for CLI plotting
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Set random seed for reproducibility
np.random.seed(42)

# Number of Monte Carlo simulations
N = 100_000

# Standard deviations for physical attributes
std_height = 1
std_reach = 1
def create_app():
    """Create and configure the Flask app that serves a small UI.
    The API endpoints allow listing available fighters and running simulations.
    """
    app = Flask(__name__, template_folder='templates', static_folder='static')

    # Initialize API (module-level) using env var or free tier
    # Prefer the documented free/demo key '123' when no env var is set
    api_key = os.getenv('THESPORTSDB_API_KEY') or '123'
    api = BoxingAPI(api_key=api_key)
    # RapidAPI/events removed

    @app.route('/')
    def index():
        # Render the UI; JS will fetch fighters and submit simulation requests
        return render_template('index.html')

    @app.route('/api/fighters')
    def list_fighters():
        return jsonify({'fighters': list(api.fighter_db.keys())})

    # /api/events removed


    @app.route('/api/simulate', methods=['POST'])
    def api_simulate():
        payload = request.get_json() or {}
        f1 = payload.get('fighter1') or payload.get('fighter1_name')
        f2 = payload.get('fighter2') or payload.get('fighter2_name')
        try:
            n = int(payload.get('n_simulations', N))
        except Exception:
            n = N
        # Multiprocessing is enabled by default server-side
        use_mp = True

        if not f1 or not f2:
            return jsonify({'error': 'fighter1 and fighter2 required'}), 400

        # Validate fighters and provide clear error messages when data is missing
        # Fetch fighter stats; if missing, create reasonable default estimates
        warnings = []
        f1_stats = api.get_fighter_stats(f1)
        f2_stats = api.get_fighter_stats(f2)
        err1 = api.validate_stats(f1_stats)
        err2 = api.validate_stats(f2_stats)
        if err1:
            # Provide a safe default so users can simulate custom fighters by name
            f1_stats = {
                'name': f1,
                'wins': 1,
                'losses': 1,
                'draws': 0,
                'total_bouts': 2,
                'ko_wins': 0,
                'height': 180,
                'reach': 180,
                'weight': 170
            }
            warnings.append(f"Fighter 1 ('{f1}') not found; using estimated default stats.")
        if err2:
            f2_stats = {
                'name': f2,
                'wins': 1,
                'losses': 1,
                'draws': 0,
                'total_bouts': 2,
                'ko_wins': 0,
                'height': 180,
                'reach': 180,
                'weight': 170
            }
            warnings.append(f"Fighter 2 ('{f2}') not found; using estimated default stats.")

        # Build DataFrames from validated stats and compute derived rates
        f1_df = pd.DataFrame([f1_stats])
        f2_df = pd.DataFrame([f2_stats])
        # Ensure totals are safe (validate_stats already adjusts total_bouts)
        for df in (f1_df, f2_df):
            tb = df.at[0, 'total_bouts'] if 'total_bouts' in df.columns else 1
            wins = df.at[0, 'wins'] if 'wins' in df.columns else 0
            ko_wins = df.at[0, 'ko_wins'] if 'ko_wins' in df.columns else 0
            df['win_rate'] = wins / tb if tb and tb > 0 else 0
            df['ko_rate'] = ko_wins / tb if tb and tb > 0 else 0

        # Cap simulations for web responsiveness
        if n > 200_000:
            n = 200_000

        results = monte_carlo_simulation(f1_df, f2_df, n_simulations=n, use_multiprocessing=use_mp)

        # Save a server-side matplotlib PNG for quick preview
        try:
            plot_path = os.path.join('static', 'last_plot.png')
            save_plot_png(results, f1, f2, plot_path)
            plot_url = f"/static/last_plot.png"
        except Exception:
            plot_url = None

        # Prepare response
        resp = {
            'results': results,
            'fighter1': f1_df.iloc[0].to_dict(),
            'fighter2': f2_df.iloc[0].to_dict(),
            'plot_url': plot_url,
            'warnings': warnings,
            'api_search_debug': {
                'fighter1': api.last_search_debug.get(f1, []),
                'fighter2': api.last_search_debug.get(f2, [])
            }
        }
        return jsonify(resp)

    return app


class BoxingAPI:
    """Boxing API wrapper and local fallback database."""
    def __init__(self, api_key=None):
        # Check if premium API key is provided
        if api_key and api_key not in ['3', '123']:
            self.base_url = "https://www.thesportsdb.com/api/v2/json"
            self.api_key = api_key
            self.is_premium = True
            self.headers = {
                "X-API-KEY": f"{api_key}",
                "Content-Type": "application/json"
            }
            print(f"\n🔌 Initialized TheSportsDB API (Premium - v2)")
        else:
            # Free tier - use API key 123
            self.base_url = "https://www.thesportsdb.com/api/v1/json"
            self.api_key = api_key or '123'
            self.is_premium = False
            self.headers = {}
            print(f"\n🔌 Initialized TheSportsDB API (Free - v1, Key: {self.api_key})")

        # Fallback local database
        self.fighter_db = {
            'Terence Crawford': {'wins': 42, 'losses': 0, 'draws': 0, 'total_bouts': 42, 'height': 178, 'reach': 183, 'ko_wins': 31, 'weight': 147},
            'Anthony Joshua': {'wins': 28, 'losses': 3, 'draws': 0, 'total_bouts': 31, 'height': 198, 'reach': 208, 'ko_wins': 25, 'weight': 240},
            'Jake Paul': {'wins': 9, 'losses': 1, 'draws': 0, 'total_bouts': 10, 'height': 185, 'reach': 193, 'ko_wins': 6, 'weight': 190},
            'Tyson Fury': {'wins': 34, 'losses': 0, 'draws': 1, 'total_bouts': 35, 'height': 206, 'reach': 216, 'ko_wins': 24, 'weight': 270},
            'Canelo Alvarez': {'wins': 62, 'losses': 2, 'draws': 2, 'total_bouts': 66, 'height': 173, 'reach': 179, 'ko_wins': 39, 'weight': 168},
            'Mike Tyson': {'wins': 50, 'losses': 6, 'draws': 0, 'total_bouts': 56, 'height': 178, 'reach': 180, 'ko_wins': 44, 'weight': 220},
            'Floyd Mayweather': {'wins': 50, 'losses': 0, 'draws': 0, 'total_bouts': 50, 'height': 173, 'reach': 183, 'ko_wins': 27, 'weight': 147}
        }
        # store debug info for last searches
        self.last_search_debug = {}

    def _convert_height(self, height_str):
        """Convert height string to cm"""
        if not height_str:
            return 180
        
        try:
            height_str = str(height_str).strip()
            
            # Already in cm
            if 'cm' in height_str.lower():
                return int(height_str.lower().replace('cm', '').strip())
            
            # Convert from feet and inches
            if 'ft' in height_str or "'" in height_str:
                # Remove common formats: 6ft 2in, 6'2", 6' 2"
                height_str = height_str.replace('ft', "'").replace('in', '"')
                height_str = height_str.replace('"', '').strip()
                
                if "'" in height_str:
                    parts = height_str.split("'")
                    feet = int(parts[0].strip())
                    inches = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0
                    return int((feet * 12 + inches) * 2.54)
            
            # Try to parse as direct number
            return int(float(height_str))
            
        except Exception as e:
            print(f"  Warning: Could not parse height '{height_str}': {e}")
            return 180
    
    def _convert_weight(self, weight_str):
        """Convert weight string to lbs"""
        if not weight_str:
            return 160
        
        try:
            weight_str = str(weight_str).strip()
            
            # Already in lbs
            if 'lbs' in weight_str.lower() or 'lb' in weight_str.lower():
                return int(weight_str.lower().replace('lbs', '').replace('lb', '').strip())
            
            # Convert from kg
            if 'kg' in weight_str.lower():
                kg = float(weight_str.lower().replace('kg', '').strip())
                return int(kg * 2.20462)
            
            # Try to parse as direct number
            return int(float(weight_str))
            
        except Exception as e:
            print(f"  Warning: Could not parse weight '{weight_str}': {e}")
            return 160
    
    def _estimate_reach(self, height_cm):
        """
        Estimate reach based on height
        Average reach is approximately equal to height
        """
        return height_cm

    def search_fighter(self, fighter_name):
        """
        Search for fighter by name using TheSportsDB API (premium or free)
        Try multiple endpoint variants and report response keys for better
        compatibility. Do not silently fallback to local DB here.
        """
        print(f"\n🔍 Searching for fighter: {fighter_name}")
        try:
            params = {"p": fighter_name}

            # Build candidate URLs to try (covers v1/v2 and presence/absence of key in path)
            candidates = []
            if self.is_premium:
                candidates.append((f"{self.base_url}/searchplayers.php", True))
                candidates.append((f"{self.base_url}/all/searchplayers.php", True))
            else:
                # v1: base_url already is https://www.thesportsdb.com/api/v1/json
                candidates.append((f"{self.base_url}/{self.api_key}/searchplayers.php", False))
                candidates.append((f"{self.base_url}/searchplayers.php", False))

            for url, use_headers in candidates:
                try:
                    if use_headers:
                        response = requests.get(url, headers=self.headers, params=params, timeout=10)
                    else:
                        response = requests.get(url, params=params, timeout=10)
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    print(f"  → Request to {url} failed: {e}")
                    continue

                try:
                    data = response.json()
                except Exception as e:
                    print(f"  → Failed to decode JSON from {url}: {e}")
                    continue

                # TheSportsDB returns 'player' containing a list
                players = data.get('player') or data.get('players') or []
                # Debug: show top-level keys received (helps diagnose format changes)
                top_keys = list(data.keys()) if isinstance(data, dict) else []
                print(f"  → API response keys from {url}: {top_keys}")
                # record debug info for this fighter
                self.last_search_debug[fighter_name] = self.last_search_debug.get(fighter_name, []) + [{
                    'url': url,
                    'status_code': response.status_code,
                    'top_keys': top_keys,
                    'players_returned': len(players) if isinstance(players, list) else 0
                }]

                if players and len(players) > 0:
                    print(f"✓ Found fighter in TheSportsDB API via {url}")
                    return players[0]

            # No candidate returned results
            print(f"⚠ Fighter not found in API after trying endpoints.")
            return None

        except requests.exceptions.RequestException as e:
            print(f"⚠ API Error: {e}")
            print(f"→ Falling back to local database...")
            return None

    def validate_stats(self, stats):
        """Return None if stats are sufficient, otherwise an error string."""
        if not stats:
            return "Fighter not found in API or local database."

        # Ensure callers can safely divide by total_bouts; if it's zero, treat
        # it as one (this happens when API returns a player but no bout records).
        if stats.get('total_bouts', 0) == 0:
            stats['total_bouts'] = 1

        # Accept API-returned players even if their win/loss/draw counts are zero;
        # simulation will use the provided (or defaulted) values.
        return None
    
    def get_fighter_stats(self, fighter_name):
        """
        Fetch fighter statistics from API or local database
        """
        # Try API first
        player_data = self.search_fighter(fighter_name)
        
        if player_data:
            # Parse API data
            try:
                wins = int(player_data.get('intWin', 0) or 0)
                losses = int(player_data.get('intLoss', 0) or 0)
                draws = int(player_data.get('intDraw', 0) or 0)
                
                # Handle KO data - might be in different fields
                ko_wins = int(player_data.get('intKO', 0) or 0)
                if ko_wins == 0:
                    # Estimate KO wins as 60% of total wins if not available
                    ko_wins = int(wins * 0.6)
                
                height = self._convert_height(player_data.get('strHeight'))
                weight = self._convert_weight(player_data.get('strWeight'))
                reach = self._estimate_reach(height)  # Estimate reach from height
                
                total_bouts = wins + losses + draws

                # If API returns no bout data, optionally fall back to local DB
                # to use a curated record (useful for well-known fighters). Set
                # env var USE_LOCAL_DB_FALLBACK=false to disable this behavior.
                if total_bouts == 0:
                    use_local_fallback = os.getenv('USE_LOCAL_DB_FALLBACK', 'true').lower() in ('1', 'true', 'yes')
                    if use_local_fallback and fighter_name in self.fighter_db:
                        print("⚠ API returned no bout records. Using local DB fallback for this fighter.")
                        stats = self.fighter_db[fighter_name].copy()
                        stats['name'] = fighter_name
                        stats['source'] = 'local_db'
                        return stats
                    else:
                        print("⚠ API returned no bout records. Proceeding with API data and using safe defaults to avoid division by zero.")
                        total_bouts = 1
                
                stats = {
                    'name': player_data.get('strPlayer', fighter_name),
                    'wins': wins,
                    'losses': losses,
                    'draws': draws,
                    'total_bouts': total_bouts,
                    'ko_wins': ko_wins,
                    'height': height,
                    'reach': reach,
                    'weight': weight,
                    'source': 'api',
                    'nationality': player_data.get('strNationality', 'Unknown'),
                    'birth_location': player_data.get('strBirthLocation', 'Unknown')
                }
                
                print(f"✓ Loaded stats from API:")
                print(f"  Record: {wins}-{losses}-{draws}")
                print(f"  Height: {height} cm")
                print(f"  Weight: {weight} lbs")
                
                return stats
                
            except Exception as e:
                print(f"⚠ Error parsing API data: {e}")
                print(f"→ Trying local database...")
        
        # No API data found. If local DB has an entry, use it as a fallback
        # (useful offline or for curated fighters). Otherwise return None.
        if fighter_name in self.fighter_db:
            print(f"⚠ No API data for '{fighter_name}'; using local DB fallback.")
            stats = self.fighter_db[fighter_name].copy()
            stats['name'] = fighter_name
            stats['source'] = 'local_db'
            return stats

        print(f"✗ Fighter '{fighter_name}' not found in API or local DB.")
        return None
    
    def create_dataframe(self, fighter_name):
        """
        Create a pandas DataFrame with fighter statistics
        """
        stats = self.get_fighter_stats(fighter_name)
        if stats:
            df = pd.DataFrame([stats])
            df['win_rate'] = df['wins'] / df['total_bouts']
            df['ko_rate'] = df['ko_wins'] / df['total_bouts']
            return df
        return None


def simulate_batch(batch_size, f1_stats, f2_stats, std_f1_win, std_f2_win, 
                   std_f1_ko, std_f2_ko, fighter1_win, fighter2_win, 
                   ko_fighter1, ko_fighter2):
    """
    Simulate a batch of fights for parallel processing
    """
    fighter1_wins = 0
    fighter2_wins = 0
    draws = 0
    
    for _ in range(batch_size):
        # Sample win rates with variance
        f1_win_sample = np.random.normal(fighter1_win, std_f1_win)
        f2_win_sample = np.random.normal(fighter2_win, std_f2_win)
        
        # Sample KO rates with variance
        f1_ko_sample = np.random.normal(ko_fighter1, std_f1_ko)
        f2_ko_sample = np.random.normal(ko_fighter2, std_f2_ko)
        
        # Sample physical attributes with variance
        f1_height_sample = np.random.normal(f1_stats['height'], std_height)
        f2_height_sample = np.random.normal(f2_stats['height'], std_height)
        f1_reach_sample = np.random.normal(f1_stats['reach'], std_reach)
        f2_reach_sample = np.random.normal(f2_stats['reach'], std_reach)
        
        # Calculate advantages
        height_advantage = (f1_height_sample - f2_height_sample) / 200
        reach_advantage = (f1_reach_sample - f2_reach_sample) / 200
        
        # Calculate fight scores with weighted factors
        fighter1_score = (
            f1_win_sample * 0.50 +      # Historical win rate (50%)
            f1_ko_sample * 0.25 +        # KO power (25%)
            height_advantage * 0.125 +   # Height advantage (12.5%)
            reach_advantage * 0.125      # Reach advantage (12.5%)
        )
        
        fighter2_score = (
            f2_win_sample * 0.50 +
            f2_ko_sample * 0.25 -
            height_advantage * 0.125 -
            reach_advantage * 0.125
        )
        
        # Add random variance to simulate fight unpredictability
        fighter1_score += np.random.normal(0, 0.1)
        fighter2_score += np.random.normal(0, 0.1)
        
        # Determine winner
        if abs(fighter1_score - fighter2_score) < 0.05:
            draws += 1
        elif fighter1_score > fighter2_score:
            fighter1_wins += 1
        else:
            fighter2_wins += 1
    
    return (fighter1_wins, fighter2_wins, draws)


def monte_carlo_simulation(fighter1_df, fighter2_df, n_simulations=N, use_multiprocessing=True):
    """
    Run Monte Carlo simulation to predict fight outcomes with optional multiprocessing
    """
    
    # Extract fighter statistics
    f1_stats = fighter1_df.iloc[0].to_dict()
    f2_stats = fighter2_df.iloc[0].to_dict()
    
    # Calculate win rates
    fighter1_win = f1_stats['wins'] / f1_stats['total_bouts']
    fighter2_win = f2_stats['wins'] / f2_stats['total_bouts']
    
    # Calculate standard deviations for win rates (using binomial distribution)
    std_fighter1_win = np.sqrt(fighter1_win * (1 - fighter1_win) / f1_stats['total_bouts'])
    std_fighter2_win = np.sqrt(fighter2_win * (1 - fighter2_win) / f2_stats['total_bouts'])
    
    # Calculate KO rates
    ko_fighter1 = f1_stats['ko_wins'] / f1_stats['wins'] if f1_stats['wins'] > 0 else 0
    ko_fighter2 = f2_stats['ko_wins'] / f2_stats['wins'] if f2_stats['wins'] > 0 else 0
    
    # Calculate standard deviations for KO rates
    std_fighter1_ko = np.sqrt(ko_fighter1 * (1 - ko_fighter1) / f1_stats['wins']) if f1_stats['wins'] > 0 else 0
    std_fighter2_ko = np.sqrt(ko_fighter2 * (1 - ko_fighter2) / f2_stats['wins']) if f2_stats['wins'] > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"MONTE CARLO BOXING SIMULATION")
    print(f"{'='*60}")
    print(f"Number of simulations: {n_simulations:,}")
    print(f"Multiprocessing: {'Enabled' if use_multiprocessing else 'Disabled'}")
    if use_multiprocessing:
        print(f"CPU cores available: {cpu_count()}")
    print(f"\nFighter 1 Stats:")
    print(f"  Name: {f1_stats.get('name', 'Unknown')}")
    print(f"  Win Rate: {fighter1_win:.3f} ± {std_fighter1_win:.3f}")
    print(f"  KO Rate: {ko_fighter1:.3f} ± {std_fighter1_ko:.3f}")
    print(f"  Height: {f1_stats['height']} cm (σ = {std_height})")
    print(f"  Reach: {f1_stats['reach']} cm (σ = {std_reach})")
    
    print(f"\nFighter 2 Stats:")
    print(f"  Name: {f2_stats.get('name', 'Unknown')}")
    print(f"  Win Rate: {fighter2_win:.3f} ± {std_fighter2_win:.3f}")
    print(f"  KO Rate: {ko_fighter2:.3f} ± {std_fighter2_ko:.3f}")
    print(f"  Height: {f2_stats['height']} cm (σ = {std_height})")
    print(f"  Reach: {f2_stats['reach']} cm (σ = {std_reach})")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    
    if use_multiprocessing:
        # Use multiprocessing for faster computation
        num_cores = min(cpu_count(), n_simulations)

        # Distribute simulations evenly across cores, handling remainder
        base_batch = n_simulations // num_cores
        remainder = n_simulations % num_cores
        batch_sizes = [base_batch + (1 if i < remainder else 0) for i in range(num_cores)]

        print(f"Running {n_simulations:,} simulations across {num_cores} cores...")
        print(f"Batch sizes per core: {[f'{b:,}' for b in batch_sizes]}\n")

        # Prepare argument tuples for starmap
        args = [(
            batch_sizes[i],
            f1_stats,
            f2_stats,
            std_fighter1_win,
            std_fighter2_win,
            std_fighter1_ko,
            std_fighter2_ko,
            fighter1_win,
            fighter2_win,
            ko_fighter1,
            ko_fighter2
        ) for i in range(num_cores)]

        # Run simulations in parallel using starmap
        with Pool(num_cores) as pool:
            results_list = pool.starmap(simulate_batch, args)

        # Aggregate results
        fighter1_wins = sum(r[0] for r in results_list)
        fighter2_wins = sum(r[1] for r in results_list)
        draws = sum(r[2] for r in results_list)
        
    else:
        # Single-threaded execution
        print(f"Running {n_simulations:,} simulations (single-threaded)...\n")
        fighter1_wins, fighter2_wins, draws = simulate_batch(
            n_simulations,
            f1_stats,
            f2_stats,
            std_fighter1_win,
            std_fighter2_win,
            std_fighter1_ko,
            std_fighter2_ko,
            fighter1_win,
            fighter2_win,
            ko_fighter1,
            ko_fighter2
        )
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    print(f"✓ Simulation completed in {execution_time:.2f} seconds")
    throughput = n_simulations / execution_time if execution_time > 0 else float('inf')
    print(f"  Throughput: {throughput:,.0f} simulations/second\n")
    
    # Calculate percentages
    fighter1_win_pct = (fighter1_wins / n_simulations) * 100
    fighter2_win_pct = (fighter2_wins / n_simulations) * 100
    draw_pct = (draws / n_simulations) * 100
    
    results = {
        'fighter1_wins': fighter1_wins,
        'fighter2_wins': fighter2_wins,
        'draws': draws,
        'fighter1_win_pct': fighter1_win_pct,
        'fighter2_win_pct': fighter2_win_pct,
        'draw_pct': draw_pct,
        'execution_time': execution_time,
        'throughput': (n_simulations / execution_time) if execution_time > 0 else float('inf')
    }
    
    return results


def plot_results(results, fighter1_name, fighter2_name):
    """
    Plot Monte Carlo simulation results using matplotlib
    Creates a bar chart similar to the image provided
    """
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Data for plotting
    fighters = [fighter1_name, fighter2_name]
    frequencies = [results['fighter1_wins'], results['fighter2_wins']]
    
    # Create bar chart with green color
    bars = ax.bar(fighters, frequencies, color='#22AA22', edgecolor='black', linewidth=1.5)
    
    # Customize plot
    ax.set_xlabel('Fighter', fontsize=14, fontweight='bold')
    ax.set_ylabel('Frequency', fontsize=14, fontweight='bold')
    ax.set_title('Monte Carlo Fight Outcome Distribution', fontsize=16, fontweight='bold', pad=20)
    
    # Add grid
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Format y-axis with comma separators
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height):,}',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    # Set background color
    ax.set_facecolor('#F5F5F5')
    fig.patch.set_facecolor('white')
    
    plt.tight_layout()
    plt.show()
    
    return fig


def save_plot_png(results, fighter1_name, fighter2_name, filepath):
    """Save a simple matplotlib bar chart of the results to `filepath`."""
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [fighter1_name, fighter2_name, 'Draws']
    values = [results['fighter1_wins'], results['fighter2_wins'], results['draws']]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel('Wins')
    ax.set_title('Monte Carlo Simulation Results')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., h, f"{int(h):,}", ha='center', va='bottom')
    fig.tight_layout()
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    fig.savefig(filepath)
    plt.close(fig)


def print_results(results, fighter1_name, fighter2_name):
    """
    Print detailed simulation results
    """
    print(f"\n{'='*60}")
    print(f"SIMULATION RESULTS")
    print(f"{'='*60}")
    print(f"\n{fighter1_name}:")
    print(f"  Wins: {results['fighter1_wins']:,} ({results['fighter1_win_pct']:.2f}%)")
    
    print(f"\n{fighter2_name}:")
    print(f"  Wins: {results['fighter2_wins']:,} ({results['fighter2_win_pct']:.2f}%)")
    
    print(f"\nDraws: {results['draws']:,} ({results['draw_pct']:.2f}%)")
    
    print(f"\nPerformance Metrics:")
    print(f"  Execution Time: {results['execution_time']:.2f} seconds")
    print(f"  Throughput: {results['throughput']:,.0f} simulations/second")
    print(f"{'='*60}\n")
    
    # Determine favorite
    if results['fighter1_win_pct'] > results['fighter2_win_pct']:
        favorite = fighter1_name
        odds = results['fighter1_win_pct']
        underdog = fighter2_name
        underdog_odds = results['fighter2_win_pct']
    else:
        favorite = fighter2_name
        odds = results['fighter2_win_pct']
        underdog = fighter1_name
        underdog_odds = results['fighter1_win_pct']
    
    print(f"🥊 PREDICTION: {favorite} is favored to win ({odds:.2f}% probability)")
    print(f"📊 {underdog} has a {underdog_odds:.2f}% chance (underdog)")
    
    # Calculate implied odds (guard against zero probabilities)
    fav_odds_decimal = (100 / odds) if odds > 0 else float('inf')
    dog_odds_decimal = (100 / underdog_odds) if underdog_odds > 0 else float('inf')
    
    print(f"\n💰 Implied Betting Odds:")
    fav_str = f"{fav_odds_decimal:.2f} to 1" if odds > 0 else "N/A"
    dog_str = f"{dog_odds_decimal:.2f} to 1" if underdog_odds > 0 else "N/A"
    print(f"  {favorite}: {fav_str}")
    print(f"  {underdog}: {dog_str}")
    print(f"{'='*60}\n")


def main():
    """
    Main function to run the boxing Monte Carlo simulation
    """
    print("\n" + "="*60)
    print("🥊 BOXING MONTE CARLO PREDICTION SYSTEM 🥊")
    print("Powered by TheSportsDB API")
    print("="*60)
    
    # Check for API key in environment variable
    api_key = os.getenv('THESPORTSDB_API_KEY')
    
    if not api_key:
        print("\n💡 No API key found. Using free tier.")
        print("   To use premium features, set THESPORTSDB_API_KEY environment variable")
        api_key = '3'  # Free tier
    else:
        print(f"\n✓ Premium API key detected!")
    
    # Initialize API
    api = BoxingAPI(api_key=api_key)
    
    # Get available fighters
    available_fighters = list(api.fighter_db.keys())
    print("\n📋 Available fighters in local database:")
    for i, fighter in enumerate(available_fighters, 1):
        print(f"  {i}. {fighter}")
    
    print("\n💡 Tip: You can search for ANY fighter by name!")
    print("   The API will search TheSportsDB database first.")
    
    # Get fighter names from user
    print("\n" + "-"*60)
    print("Enter fighter names (or press Enter for default matchup)")
    print("-"*60)
    fighter1_name = input("Fighter 1 [Anthony Joshua]: ").strip() or "Anthony Joshua"
    fighter2_name = input("Fighter 2 [Jake Paul]: ").strip() or "Jake Paul"
    
    # Ask about multiprocessing
    use_mp = input("\nUse multiprocessing for faster simulation? [Y/n]: ").strip().lower()
    use_multiprocessing = use_mp != 'n'
    
    print("\n" + "="*60)
    
    # Create DataFrames for fighters
    fighter1_df = api.create_dataframe(fighter1_name)
    fighter2_df = api.create_dataframe(fighter2_name)
    
    if fighter1_df is None or fighter2_df is None:
        print("\n❌ Error: One or both fighters not found.")
        print(f"\n💡 Try one of these fighters:")
        for name in available_fighters:
            print(f"   • {name}")
        return
    
    # Run Monte Carlo simulation
    results = monte_carlo_simulation(fighter1_df, fighter2_df, N, use_multiprocessing)
    
    # Print results
    print_results(results, fighter1_name, fighter2_name)
    
    # Plot results
    print("📊 Generating visualization...")
    plot_results(results, fighter1_name, fighter2_name)
    
    # Display detailed statistics
    print("\n" + "="*60)
    print("DETAILED FIGHTER STATISTICS")
    print("="*60)
    print(f"\n{fighter1_name}:")
    print(fighter1_df.to_string(index=False))
    print(f"\n{fighter2_name}:")
    print(fighter2_df.to_string(index=False))
    print("\n" + "="*60)
    print("Simulation Complete! 🎉")
    print("="*60 + "\n")


if __name__ == '__main__':
    import sys
    # Default: run web UI. Pass `cli` to run the interactive CLI instead.
    if len(sys.argv) > 1 and sys.argv[1] == 'cli':
        main()
    else:
        app = create_app()
        # Allow overriding via environment variable `PORT`, default to 5001 to avoid conflicts
        try:
            port = int(os.getenv('PORT', '5001'))
        except Exception:
            port = 5001
        app.run(host='0.0.0.0', port=port, debug=True)