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
        # Fetch fighter stats; if missing, return error
        warnings = []
        f1_stats = api.get_fighter_stats(f1)
        f2_stats = api.get_fighter_stats(f2)
        
        # Check for missing fighters - if not in local DB and no good API data, reject
        if not f1_stats:
            return jsonify({
                'error': f"Fighter '{f1}' not found via API or schedule search.",
                'suggestion': "Please check the spelling and try again.",
                'available_fighters': list(api.fighter_db.keys()),
                'debug': api.last_search_debug.get(f1, [])
            }), 404
        if not f2_stats:
            return jsonify({
                'error': f"Fighter '{f2}' not found via API or schedule search.",
                'suggestion': "Please check the spelling and try again.",
                'available_fighters': list(api.fighter_db.keys()),
                'debug': api.last_search_debug.get(f2, [])
            }), 404

        # Build DataFrames from validated stats and compute derived rates
        f1_df = pd.DataFrame([f1_stats])
        f2_df = pd.DataFrame([f2_stats])
        # Ensure totals are safe (validate_stats already adjusts total_bouts)
        for df in (f1_df, f2_df):
            tb = df.at[0, 'total_bouts'] if 'total_bouts' in df.columns else 1
            wins = df.at[0, 'wins'] if 'wins' in df.columns else 0
            ko_wins = df.at[0, 'ko_wins'] if 'ko_wins' in df.columns else 0
            df['win_rate'] = wins / tb if tb and tb > 0 else 0
            # FIXED: KO rate should be KO wins out of total bouts, not just wins
            # This prevents sample size bias (e.g., 4 wins/4 KOs shouldn't be compared to 45 wins/40 KOs)
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

        # Check for significant weight class differences and add warning
        weight_diff = abs(f2_stats.get('weight', 170) - f1_stats.get('weight', 170))
        if weight_diff > 25:  # Significant weight class difference
            weight_classes = round(weight_diff / 15)
            heavier_fighter = f2_stats.get('name', 'Fighter 2') if f2_stats.get('weight', 170) > f1_stats.get('weight', 170) else f1_stats.get('name', 'Fighter 1')
            heavier_pct = results['fighter2_win_pct'] if f2_stats.get('weight', 170) > f1_stats.get('weight', 170) else results['fighter1_win_pct']
            
            warnings.append(f"⚠️  WEIGHT CLASS NOTICE: {heavier_fighter} is ~{weight_classes} weight class{'es' if weight_classes > 1 else ''} heavier ({weight_diff} lbs). "
                          f"This significantly favors {heavier_fighter} ({heavier_pct:.1f}% win rate). "
                          f"Results are influenced by physical class advantage, not just skill.")

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
            # --- Your original core guys (updated with real stats) ---
            'Terence Crawford': {
                'wins': 42, 'losses': 0, 'draws': 0, 'total_bouts': 42,
                'height': 173, 'reach': 188, 'ko_wins': 31, 'weight': 168
            },
            'Anthony Joshua': {
                'wins': 29, 'losses': 4, 'draws': 0, 'total_bouts': 33,
                'height': 198, 'reach': 208, 'ko_wins': 26, 'weight': 245
            },
            'Jake Paul': {
                'wins': 9, 'losses': 1, 'draws': 0, 'total_bouts': 10,
                'height': 185, 'reach': 193, 'ko_wins': 6, 'weight': 190
            },
            'Tyson Fury': {
                'wins': 34, 'losses': 2, 'draws': 1, 'total_bouts': 37,
                'height': 206, 'reach': 216, 'ko_wins': 24, 'weight': 270
            },
            'Canelo Alvarez': {
                'wins': 63, 'losses': 3, 'draws': 2, 'total_bouts': 68,
                'height': 171, 'reach': 179, 'ko_wins': 39, 'weight': 168
            },
            'Mike Tyson': {
                'wins': 50, 'losses': 6, 'draws': 0, 'total_bouts': 56,
                'height': 178, 'reach': 180, 'ko_wins': 44, 'weight': 220
            },
            'Floyd Mayweather': {
                'wins': 50, 'losses': 0, 'draws': 0, 'total_bouts': 50,
                'height': 173, 'reach': 183, 'ko_wins': 27, 'weight': 147
            },
            'Manny Pacquiao': {
                'wins': 62, 'losses': 8, 'draws': 2, 'total_bouts': 72,
                'height': 168, 'reach': 170, 'ko_wins': 39, 'weight': 147
            },
            'Evander Holyfield': {
                'wins': 44, 'losses': 10, 'draws': 2, 'total_bouts': 56,
                'height': 189, 'reach': 198, 'ko_wins': 29, 'weight': 215
            },

            # --- Heavyweight legends / stars ---

            'Muhammad Ali': {
                'wins': 56, 'losses': 5, 'draws': 0, 'total_bouts': 61,
                'height': 191, 'reach': 198, 'ko_wins': 37, 'weight': 212
            },
            'Joe Frazier': {
                'wins': 32, 'losses': 4, 'draws': 1, 'total_bouts': 37,
                'height': 182, 'reach': 185, 'ko_wins': 27, 'weight': 205
            },
            'George Foreman': {
                'wins': 76, 'losses': 5, 'draws': 0, 'total_bouts': 81,
                'height': 191, 'reach': 199, 'ko_wins': 68, 'weight': 220
            },
            'Larry Holmes': {
                'wins': 69, 'losses': 6, 'draws': 0, 'total_bouts': 75,
                'height': 191, 'reach': 206, 'ko_wins': 44, 'weight': 210
            },
            'Lennox Lewis': {
                'wins': 41, 'losses': 2, 'draws': 1, 'total_bouts': 44,
                'height': 196, 'reach': 213, 'ko_wins': 32, 'weight': 245
            },
            'Wladimir Klitschko': {
                'wins': 64, 'losses': 5, 'draws': 0, 'total_bouts': 69,
                'height': 198, 'reach': 206, 'ko_wins': 53, 'weight': 245
            },
            'Vitali Klitschko': {
                'wins': 45, 'losses': 2, 'draws': 0, 'total_bouts': 47,
                'height': 201, 'reach': 201, 'ko_wins': 41, 'weight': 245
            },
            'Deontay Wilder': {
                'wins': 43, 'losses': 3, 'draws': 1, 'total_bouts': 47,
                'height': 201, 'reach': 211, 'ko_wins': 42, 'weight': 220
            },
            'Oleksandr Usyk': {
                'wins': 24, 'losses': 0, 'draws': 0, 'total_bouts': 24,
                'height': 191, 'reach': 198, 'ko_wins': 15, 'weight': 220
            },
            'Andy Ruiz Jr': {
                'wins': 35, 'losses': 2, 'draws': 0, 'total_bouts': 37,
                'height': 188, 'reach': 188, 'ko_wins': 22, 'weight': 260
            },
            'Riddick Bowe': {
                'wins': 43, 'losses': 1, 'draws': 0, 'total_bouts': 44,
                'height': 196, 'reach': 206, 'ko_wins': 33, 'weight': 240
            },
            'Sonny Liston': {
                'wins': 50, 'losses': 4, 'draws': 0, 'total_bouts': 54,
                'height': 185, 'reach': 213, 'ko_wins': 39, 'weight': 215
            },
            'Joe Louis': {
                'wins': 66, 'losses': 3, 'draws': 0, 'total_bouts': 69,
                'height': 188, 'reach': 193, 'ko_wins': 52, 'weight': 205
            },
            'Rocky Marciano': {
                'wins': 49, 'losses': 0, 'draws': 0, 'total_bouts': 49,
                'height': 180, 'reach': 173, 'ko_wins': 43, 'weight': 188
            },

            # --- Middle / super-middle / light-heavy stars ---

            'Gennady Golovkin': {
                'wins': 42, 'losses': 2, 'draws': 1, 'total_bouts': 45,
                'height': 179, 'reach': 178, 'ko_wins': 37, 'weight': 160
            },
            'Andre Ward': {
                'wins': 32, 'losses': 0, 'draws': 0, 'total_bouts': 32,
                'height': 183, 'reach': 180, 'ko_wins': 16, 'weight': 175
            },
            'Bernard Hopkins': {
                'wins': 55, 'losses': 8, 'draws': 2, 'total_bouts': 65,
                'height': 185, 'reach': 191, 'ko_wins': 32, 'weight': 175
            },
            'Roy Jones Jr': {
                'wins': 66, 'losses': 9, 'draws': 0, 'total_bouts': 75,
                'height': 180, 'reach': 188, 'ko_wins': 47, 'weight': 175
            },
            'James Toney': {
                'wins': 77, 'losses': 10, 'draws': 3, 'total_bouts': 90,
                'height': 178, 'reach': 190, 'ko_wins': 47, 'weight': 168
            },
            'David Benavidez': {
                'wins': 30, 'losses': 0, 'draws': 0, 'total_bouts': 30,
                'height': 187, 'reach': 189, 'ko_wins': 24, 'weight': 168
            },
            'Caleb Plant': {
                'wins': 22, 'losses': 2, 'draws': 0, 'total_bouts': 24,
                'height': 185, 'reach': 188, 'ko_wins': 13, 'weight': 168
            },
            'Dmitry Bivol': {
                'wins': 23, 'losses': 0, 'draws': 0, 'total_bouts': 23,
                'height': 183, 'reach': 183, 'ko_wins': 12, 'weight': 175
            },
            'Artur Beterbiev': {
                'wins': 20, 'losses': 1, 'draws': 0, 'total_bouts': 21,
                'height': 182, 'reach': 185, 'ko_wins': 20, 'weight': 175
            },
            'Joe Calzaghe': {
                'wins': 46, 'losses': 0, 'draws': 0, 'total_bouts': 46,
                'height': 183, 'reach': 185, 'ko_wins': 32, 'weight': 168
            },
            'Kelly Pavlik': {
                'wins': 40, 'losses': 2, 'draws': 0, 'total_bouts': 42,
                'height': 188, 'reach': 191, 'ko_wins': 34, 'weight': 160
            },

            # --- Welter / light-welter / lightweight stars ---

            'Sugar Ray Leonard': {
                'wins': 36, 'losses': 3, 'draws': 1, 'total_bouts': 40,
                'height': 178, 'reach': 188, 'ko_wins': 25, 'weight': 147
            },
            'Sugar Ray Robinson': {
                'wins': 174, 'losses': 19, 'draws': 6, 'total_bouts': 199,
                'height': 180, 'reach': 185, 'ko_wins': 109, 'weight': 147
            },
            'Julio Cesar Chavez': {
                'wins': 107, 'losses': 6, 'draws': 2, 'total_bouts': 115,
                'height': 171, 'reach': 173, 'ko_wins': 86, 'weight': 140
            },
            'Oscar De La Hoya': {
                'wins': 39, 'losses': 6, 'draws': 0, 'total_bouts': 45,
                'height': 179, 'reach': 185, 'ko_wins': 30, 'weight': 147
            },
            'Shane Mosley': {
                'wins': 49, 'losses': 10, 'draws': 1, 'total_bouts': 60,
                'height': 175, 'reach': 178, 'ko_wins': 41, 'weight': 147
            },
            'Miguel Cotto': {
                'wins': 41, 'losses': 6, 'draws': 0, 'total_bouts': 47,
                'height': 170, 'reach': 170, 'ko_wins': 33, 'weight': 154
            },
            'Errol Spence Jr': {
                'wins': 28, 'losses': 1, 'draws': 0, 'total_bouts': 29,
                'height': 177, 'reach': 183, 'ko_wins': 22, 'weight': 147
            },
            'Shakur Stevenson': {
                'wins': 22, 'losses': 0, 'draws': 0, 'total_bouts': 22,
                'height': 173, 'reach': 173, 'ko_wins': 10, 'weight': 135
            },
            'Terence Crawford (LW prime)': {
                'wins': 29, 'losses': 0, 'draws': 0, 'total_bouts': 29,
                'height': 173, 'reach': 188, 'ko_wins': 21, 'weight': 135
            },

            # --- Modern lightweights / super-lightweights ---

            'Devin Haney': {
                'wins': 33, 'losses': 1, 'draws': 0, 'total_bouts': 34,
                'height': 175, 'reach': 180, 'ko_wins': 15, 'weight': 140
            },
            'Teofimo Lopez': {
                'wins': 21, 'losses': 1, 'draws': 0, 'total_bouts': 22,
                'height': 173, 'reach': 174, 'ko_wins': 13, 'weight': 140
            },
            'Ryan Garcia': {
                'wins': 25, 'losses': 1, 'draws': 0, 'total_bouts': 26,
                'height': 178, 'reach': 178, 'ko_wins': 20, 'weight': 140
            },
            'Josh Taylor': {
                'wins': 19, 'losses': 2, 'draws': 0, 'total_bouts': 21,
                'height': 178, 'reach': 177, 'ko_wins': 13, 'weight': 140
            },
            'Regis Prograis': {
                'wins': 29, 'losses': 2, 'draws': 0, 'total_bouts': 31,
                'height': 173, 'reach': 170, 'ko_wins': 24, 'weight': 140
            },

            # --- Smaller weight monsters ---

            'Naoya Inoue': {
                'wins': 32, 'losses': 0, 'draws': 0, 'total_bouts': 32,
                'height': 165, 'reach': 171, 'ko_wins': 27, 'weight': 122
            },
            'Nonito Donaire': {
                'wins': 43, 'losses': 8, 'draws': 0, 'total_bouts': 51,
                'height': 170, 'reach': 174, 'ko_wins': 29, 'weight': 118
            },
            'Juan Manuel Marquez': {
                'wins': 56, 'losses': 7, 'draws': 1, 'total_bouts': 64,
                'height': 170, 'reach': 173, 'ko_wins': 40, 'weight': 135
            },
            'Marco Antonio Barrera': {
                'wins': 67, 'losses': 7, 'draws': 0, 'total_bouts': 74,
                'height': 168, 'reach': 178, 'ko_wins': 44, 'weight': 126
            },
            'Erik Morales': {
                'wins': 52, 'losses': 9, 'draws': 0, 'total_bouts': 61,
                'height': 173, 'reach': 183, 'ko_wins': 36, 'weight': 126
            },

            # --- Modern smaller guys / popular names ---

            'Gervonta Davis': {
                'wins': 30, 'losses': 0, 'draws': 1, 'total_bouts': 31,
                'height': 166, 'reach': 171, 'ko_wins': 28, 'weight': 135
            },
            'Vasiliy Lomachenko': {
                'wins': 18, 'losses': 3, 'draws': 0, 'total_bouts': 21,
                'height': 170, 'reach': 166, 'ko_wins': 11, 'weight': 135
            },
            'Oscar Valdez': {
                'wins': 32, 'losses': 2, 'draws': 0, 'total_bouts': 34,
                'height': 166, 'reach': 168, 'ko_wins': 24, 'weight': 130
            },
            'Josh Warrington': {
                'wins': 31, 'losses': 3, 'draws': 1, 'total_bouts': 35,
                'height': 170, 'reach': 170, 'ko_wins': 8, 'weight': 126
            },
            'Roman Gonzalez': {
                'wins': 51, 'losses': 4, 'draws': 0, 'total_bouts': 55,
                'height': 160, 'reach': 163, 'ko_wins': 41, 'weight': 115
            },

            # --- Charlo / PBC guys etc ---

            'Jermell Charlo': {
                'wins': 35, 'losses': 2, 'draws': 1, 'total_bouts': 38,
                'height': 180, 'reach': 185, 'ko_wins': 19, 'weight': 154
            },
            'Jermall Charlo': {
                'wins': 33, 'losses': 1, 'draws': 0, 'total_bouts': 34,
                'height': 183, 'reach': 187, 'ko_wins': 22, 'weight': 160
            },
            'Tony Harrison': {
                'wins': 29, 'losses': 4, 'draws': 1, 'total_bouts': 34,
                'height': 185, 'reach': 194, 'ko_wins': 21, 'weight': 154
            },
            'Keith Thurman': {
                'wins': 30, 'losses': 1, 'draws': 0, 'total_bouts': 31,
                'height': 171, 'reach': 175, 'ko_wins': 22, 'weight': 147
            },

            # --- A few more fan-favorites to bulk it out ---

            'Amir Khan': {
                'wins': 34, 'losses': 6, 'draws': 0, 'total_bouts': 40,
                'height': 173, 'reach': 180, 'ko_wins': 21, 'weight': 147
            },
            'Kell Brook': {
                'wins': 40, 'losses': 3, 'draws': 0, 'total_bouts': 43,
                'height': 175, 'reach': 175, 'ko_wins': 28, 'weight': 147
            },
            'Adrien Broner': {
                'wins': 35, 'losses': 4, 'draws': 1, 'total_bouts': 40,
                'height': 170, 'reach': 177, 'ko_wins': 24, 'weight': 140
            },
            'Tim Tszyu': {
                'wins': 25, 'losses': 1, 'draws': 0, 'total_bouts': 26,
                'height': 174, 'reach': 179, 'ko_wins': 17, 'weight': 154
            },
            'Vergil Ortiz Jr': {
                'wins': 21, 'losses': 0, 'draws': 0, 'total_bouts': 21,
                'height': 178, 'reach': 180, 'ko_wins': 21, 'weight': 154
            }
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

    def _find_local_fighter_key(self, fighter_name):
        """Return the exact key from `fighter_db` matching `fighter_name` (case-insensitive), or None."""
        if not fighter_name:
            return None
        lname = fighter_name.strip().lower()
        for key in self.fighter_db:
            if key.lower() == lname:
                return key
        return None

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

    def search_rapidapi_schedule(self, fighter_name):
        """
        Search the RapidAPI boxing events schedule for a fighter name.
        This is used as a fallback when TheSportsDB returns no player info
        — it helps detect recently announced fighters on upcoming cards.
        Returns a small dict when matched, otherwise None.
        """
        print(f"\n🔎 Searching RapidAPI schedule for: {fighter_name}")
        # Allow override via env var RAPIDAPI_KEY; fall back to a bundled key if not set
        rapid_key = os.getenv('RAPIDAPI_KEY') or '954b586842msha9c5947f76e426bp13b543jsnd28cc99ca940'
        url = 'https://boxing-data-api.p.rapidapi.com/v1/events/schedule'
        params = {'days': 7, 'past_hours': 12, 'date_sort': 'ASC', 'page_num': 1, 'page_size': 25}
        headers = {
            'x-rapidapi-host': 'boxing-data-api.p.rapidapi.com',
            'x-rapidapi-key': rapid_key
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  → RapidAPI schedule request failed: {e}")
            # record debug and return None
            self.last_search_debug[fighter_name] = self.last_search_debug.get(fighter_name, []) + [{
                'source': 'rapidapi.schedule', 'error': str(e)
            }]
            return None

        # Try to find the fighter name anywhere in the returned payload
        def _find(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    if _find(v):
                        return True
            elif isinstance(obj, list):
                for it in obj:
                    if _find(it):
                        return True
            elif isinstance(obj, str):
                if fighter_name.lower() in obj.lower():
                    return True
            return False

        matched = _find(data)
        self.last_search_debug[fighter_name] = self.last_search_debug.get(fighter_name, []) + [{
            'source': 'rapidapi.schedule', 'matched': bool(matched)
        }]

        if matched:
            print(f"✓ Found name in RapidAPI schedule payload — accepting as valid fighter (minimal data).")
            return {'name': fighter_name, 'matched_event': True}

        print(f"✗ No match for {fighter_name} in RapidAPI schedule payload.")
        return None

    def search_rapidapi_fighter_details(self, fighter_name):
        """
        Query the Boxing Data API (via RapidAPI) for detailed fighter profiles.
        Try several candidate endpoints and parse the first reasonable result.
        Returns a dict of raw API fields or None.
        """
        print(f"\n🔎 Searching RapidAPI fighter details for: {fighter_name}")
        rapid_key = os.getenv('RAPIDAPI_KEY') or '954b586842msha9c5947f76e426bp13b543jsnd28cc99ca940'
        base = 'https://boxing-data-api.p.rapidapi.com'

        # Candidate endpoints and param names to try
        candidates = [
            (f"{base}/v1/fighters", {'search': fighter_name}),
            (f"{base}/v1/fighters", {'q': fighter_name}),
            (f"{base}/v1/boxers", {'search': fighter_name}),
            (f"{base}/v1/fighter", {'search': fighter_name}),
            (f"{base}/v1/fighters/search", {'name': fighter_name}),
        ]

        headers = {
            'x-rapidapi-host': 'boxing-data-api.p.rapidapi.com',
            'x-rapidapi-key': rapid_key
        }

        for url, params in candidates:
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                # record debug and continue
                self.last_search_debug[fighter_name] = self.last_search_debug.get(fighter_name, []) + [{
                    'source': 'rapidapi.fighter_details', 'url': url, 'error': str(e)
                }]
                continue

            # Record top-level keys for debugging
            top_keys = list(data.keys()) if isinstance(data, dict) else []
            self.last_search_debug[fighter_name] = self.last_search_debug.get(fighter_name, []) + [{
                'source': 'rapidapi.fighter_details', 'url': url, 'top_keys': top_keys
            }]

            # Heuristics: look for lists under common keys
            candidates_keys = []
            if isinstance(data, dict):
                for k in ('data', 'fighters', 'boxers', 'results', 'items'):
                    v = data.get(k)
                    if isinstance(v, list) and len(v) > 0:
                        candidates_keys = v
                        break

                # Or if top-level appears to be a single fighter dict
                if not candidates_keys:
                    # sometimes API returns a single object with fighter fields
                    # check for presence of name-like keys
                    if any(k in data for k in ('name', 'fighter_name', 'fullName', 'first_name')):
                        candidates_keys = [data]

            # If we found potential fighter records, pick the first and normalize
            if candidates_keys:
                candidate = candidates_keys[0]
                # Try to extract common fields
                wins = int(candidate.get('wins', candidate.get('win', 0) or 0) or 0)
                losses = int(candidate.get('losses', candidate.get('loss', 0) or 0) or 0)
                draws = int(candidate.get('draws', candidate.get('ties', 0) or 0) or 0)
                ko_wins = int(candidate.get('ko', candidate.get('kos', candidate.get('ko_wins', 0) or 0) or 0) or 0)

                # Height and weight may be in various units/keys
                height = candidate.get('height') or candidate.get('height_cm') or candidate.get('height_cm_display') or None
                weight = candidate.get('weight') or candidate.get('weight_kg') or candidate.get('weight_lb') or None

                nationality = candidate.get('nationality') or candidate.get('country') or candidate.get('country_name')
                birth_location = candidate.get('birth_place') or candidate.get('birth_location') or candidate.get('hometown')

                parsed = {
                    'name': candidate.get('name') or candidate.get('fighter_name') or fighter_name,
                    'wins': wins,
                    'losses': losses,
                    'draws': draws,
                    'total_bouts': wins + losses + draws,
                    'ko_wins': ko_wins,
                    'height': self._convert_height(height),
                    'reach': self._estimate_reach(self._convert_height(height)),
                    'weight': self._convert_weight(weight),
                    'source': 'rapidapi.fighter_details',
                    'nationality': nationality or 'Unknown',
                    'birth_location': birth_location or 'Unknown'
                }
                print(f"✓ Loaded fighter details from RapidAPI endpoint: {url}")
                return parsed

        print(f"✗ No detailed fighter profile found on RapidAPI for {fighter_name}.")
        return None

    def validate_stats(self, stats):
        """Return None if stats are sufficient, otherwise an error string."""
        if not stats:
            return "Fighter not found in API or local database."

        # Check if stats came from API with zero fights - likely a bad match
        if stats.get('total_bouts', 0) == 0 and stats.get('source') == 'rapidapi.com':
            return "Fighter found but has no bout data - likely a misspelling or non-boxer."

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
                    # If the API returns no bout records but we have a curated
                    # local entry for this fighter, prefer the curated record
                    # because it will be more accurate for well-known fighters.
                    local_key = self._find_local_fighter_key(fighter_name)
                    if local_key:
                        print("⚠ API returned no bout records. Using local curated DB for this fighter.")
                        stats = self.fighter_db[local_key].copy()
                        stats['name'] = local_key
                        stats['source'] = 'local_db'
                        return stats

                    use_local_fallback = os.getenv('USE_LOCAL_DB_FALLBACK', 'true').lower() in ('1', 'true', 'yes')
                    if use_local_fallback:
                        local_key = self._find_local_fighter_key(fighter_name)
                        if local_key:
                            print("⚠ API returned no bout records. Using local DB fallback for this fighter.")
                            stats = self.fighter_db[local_key].copy()
                            stats['name'] = local_key
                            stats['source'] = 'local_db'
                            return stats

                    # If the API provides a player entry but zero bout counts,
                    # try the RapidAPI schedule as a fallback before using
                    # conservative safe defaults. This helps when TheSportsDB
                    # contains a player stub but no bout history.
                    schedule_match = self.search_rapidapi_schedule(fighter_name)
                    if schedule_match:
                        stats = {
                            'name': fighter_name,
                            'wins': 1,
                            'losses': 0,
                            'draws': 0,
                            'total_bouts': 1,
                            'ko_wins': 0,
                            'height': 180,
                            'reach': 180,
                            'weight': 170,
                            'source': 'rapidapi.schedule'
                        }
                        print(f"✓ Created minimal stats for '{fighter_name}' from RapidAPI schedule fallback.")
                        return stats

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
                    'source': 'rapidapi.com',
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
        # No structured API player data. Try RapidAPI schedule to detect
        # recently announced or card-listed fighters (minimal safe defaults).
        # First, try fetching richer fighter details from the Boxing Data API
        # (RapidAPI) before falling back to schedule or curated DB.
        details = self.search_rapidapi_fighter_details(fighter_name)
        if details:
            return details

        schedule_match = self.search_rapidapi_schedule(fighter_name)
        if schedule_match:
            # Use conservative safe defaults so simulations can run without
            # halting for missing curated data. These defaults avoid divide-by-zero.
            stats = {
                'name': fighter_name,
                'wins': 1,
                'losses': 0,
                'draws': 0,
                'total_bouts': 1,
                'ko_wins': 0,
                'height': 180,
                'reach': 180,
                'weight': 170,
                'source': 'rapidapi.schedule'
            }
            print(f"✓ Created minimal stats for '{fighter_name}' from RapidAPI schedule fallback.")
            return stats

        # If RapidAPI schedule didn't find the fighter, optionally fall back
        # to the curated local DB only when explicitly allowed via env var.
        use_local_fallback = os.getenv('USE_LOCAL_DB_FALLBACK', 'true').lower() in ('1', 'true', 'yes')
        if use_local_fallback and fighter_name in self.fighter_db:
            print(f"⚠ No API data for '{fighter_name}'; using local DB fallback.")
            stats = self.fighter_db[fighter_name].copy()
            stats['name'] = fighter_name
            stats['source'] = 'local_db'
            return stats

        print(f"✗ Fighter '{fighter_name}' not found in API, RapidAPI schedule, or allowed local DB fallback.")
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
    Accounts for: win rate, KO power, physical attributes (height/reach), and weight class
    """
    fighter1_wins = 0
    fighter2_wins = 0
    draws = 0
    
    # Weight class advantage calculation
    # Heavier fighters have inherent advantage in strength/power
    f1_weight = f1_stats.get('weight', 170)
    f2_weight = f2_stats.get('weight', 170)
    weight_diff = abs(f2_weight - f1_weight)  # How different their weights are
    
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
        
        # Sample weight with variance (fighters naturally vary ±5 lbs)
        f1_weight_sample = np.random.normal(f1_weight, 5)
        f2_weight_sample = np.random.normal(f2_weight, 5)
        
        # Calculate advantages
        height_advantage = (f1_height_sample - f2_height_sample) / 200
        reach_advantage = (f1_reach_sample - f2_reach_sample) / 200
        
        # Weight class advantage: massive factor in boxing across different weight classes
        # Heavier fighters have more power, durability, and reach advantage
        # Formula: (fighter1_weight - fighter2_weight) / 460 (optimized for 90/10 split)
        weight_advantage = (f1_weight_sample - f2_weight_sample) / 460
        
        # Calculate fight scores with weighted factors accounting for weight class
        # Major focus on weight advantage in cross-weight-class matchups
        fighter1_score = (
            f1_win_sample * 0.37 +      # Historical win rate (37%)
            f1_ko_sample * 0.15 +        # KO power (15%)
            height_advantage * 0.08 +   # Height advantage (8%)
            reach_advantage * 0.05 +    # Reach advantage (5%)
            weight_advantage * 0.35     # Weight class advantage (35%, reduced from 50%)
        )
        
        fighter2_score = (
            f2_win_sample * 0.37 +
            f2_ko_sample * 0.15 -
            height_advantage * 0.08 -
            reach_advantage * 0.05 -
            weight_advantage * 0.35
        )
        
        # Add random variance to simulate fight unpredictability
        fighter1_score += np.random.normal(0, 0.1)
        fighter2_score += np.random.normal(0, 0.1)
        
        # Determine winner (reduced draw threshold from 0.05 to 0.02 for more decisive outcomes)
        if abs(fighter1_score - fighter2_score) < 0.02:
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
    
    # Calculate KO rates (FIXED: using total_bouts instead of wins to account for sample size)
    # This prevents bias where fighters with few fights are over/underestimated
    ko_fighter1 = f1_stats['ko_wins'] / f1_stats['total_bouts'] if f1_stats['total_bouts'] > 0 else 0
    ko_fighter2 = f2_stats['ko_wins'] / f2_stats['total_bouts'] if f2_stats['total_bouts'] > 0 else 0
    
    # Calculate standard deviations for KO rates (using total_bouts for more accurate confidence intervals)
    std_fighter1_ko = np.sqrt(ko_fighter1 * (1 - ko_fighter1) / f1_stats['total_bouts']) if f1_stats['total_bouts'] > 0 else 0
    std_fighter2_ko = np.sqrt(ko_fighter2 * (1 - ko_fighter2) / f2_stats['total_bouts']) if f2_stats['total_bouts'] > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"MONTE CARLO BOXING SIMULATION")
    print(f"{'='*60}")
    print(f"Number of simulations: {n_simulations:,}")
    print(f"Multiprocessing: {'Enabled' if use_multiprocessing else 'Disabled'}")
    if use_multiprocessing:
        print(f"CPU cores available: {cpu_count()}")
    
    # Display detailed fighter stats with weight class info
    print(f"\nFighter 1 Stats:")
    print(f"  Name: {f1_stats.get('name', 'Unknown')}")
    print(f"  Record: {f1_stats.get('wins', 0)}-{f1_stats.get('losses', 0)}-{f1_stats.get('draws', 0)} ({f1_stats.get('total_bouts', 1)} bouts)")
    print(f"  Win Rate: {fighter1_win:.1%} ± {std_fighter1_win:.3f}")
    print(f"  KO Rate: {ko_fighter1:.1%} ± {std_fighter1_ko:.3f} ({f1_stats.get('ko_wins', 0)}/{f1_stats.get('total_bouts', 1)} bouts)")
    print(f"  Weight: {f1_stats.get('weight', 170)} lbs")
    print(f"  Height: {f1_stats['height']} cm | Reach: {f1_stats['reach']} cm")
    
    print(f"\nFighter 2 Stats:")
    print(f"  Name: {f2_stats.get('name', 'Unknown')}")
    print(f"  Record: {f2_stats.get('wins', 0)}-{f2_stats.get('losses', 0)}-{f2_stats.get('draws', 0)} ({f2_stats.get('total_bouts', 1)} bouts)")
    print(f"  Win Rate: {fighter2_win:.1%} ± {std_fighter2_win:.3f}")
    print(f"  KO Rate: {ko_fighter2:.1%} ± {std_fighter2_ko:.3f} ({f2_stats.get('ko_wins', 0)}/{f2_stats.get('total_bouts', 1)} bouts)")
    print(f"  Weight: {f2_stats.get('weight', 170)} lbs")
    print(f"  Height: {f2_stats['height']} cm | Reach: {f2_stats['reach']} cm")
    
    # Show weight class advantage
    weight_diff = abs(f2_stats.get('weight', 170) - f1_stats.get('weight', 170))
    if weight_diff > 20:
        heavier = f2_stats.get('name', 'Fighter 2') if f2_stats.get('weight', 170) > f1_stats.get('weight', 170) else f1_stats.get('name', 'Fighter 1')
        print(f"\n⚠ Significant weight class difference: {weight_diff} lbs")
        print(f"  → {heavier} has weight advantage")
    
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
    
    # Check for significant weight class differences
    weight_diff = abs(f2_stats.get('weight', 170) - f1_stats.get('weight', 170))
    if weight_diff > 25:  # Significant weight class difference (more than 1 weight class)
        weight_classes = round(weight_diff / 15)  # Approximate weight classes (~15 lbs per class)
        heavier_fighter = f2_stats.get('name', 'Fighter 2') if f2_stats.get('weight', 170) > f1_stats.get('weight', 170) else f1_stats.get('name', 'Fighter 1')
        heavier_pct = fighter2_win_pct if f2_stats.get('weight', 170) > f1_stats.get('weight', 170) else fighter1_win_pct
        
        print(f"\n⚠️  WEIGHT CLASS NOTICE:")
        print(f"   {heavier_fighter} is ~{weight_classes} weight class{'es' if weight_classes > 1 else ''} heavier ({weight_diff} lbs)")
        print(f"   This significantly favors {heavier_fighter} ({heavier_pct:.1f}% win rate)")
        print(f"   Results are influenced by physical class advantage, not just skill\n")
    
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