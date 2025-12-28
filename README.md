# Boxing MonteCarlo — Fight Prediction Engine (Local + CLI + Web)

A Monte Carlo–based boxing match prediction engine that runs locally using a curated fighter database or manual fighter input. Designed for research and educational purposes — not for betting or financial advice.

**Highlights**
- CLI-first simulation engine with optional lightweight Flask web UI.
- Local `BoxingDB` containing curated fighter stats as the primary data source.
- Manual fighter input (enter Fighter 1 and Fighter 2) or select from the local DB.
- Monte Carlo simulation with multiprocessing to estimate win/draw probabilities and KO likelihoods.

**Languages & Frameworks**
- Python 3.8+
- Libraries: `numpy`, `pandas`, `matplotlib`, `multiprocessing` (stdlib), `flask` (optional web UI)
- Frontend (optional web): HTML/CSS/JavaScript (Chart.js used in the static assets)

## Quick Start

1. Install dependencies:

pip install -r requirements.txt

2. Run (CLI):

python main.py

3. Run (optional web UI):

python main.py
# then open http://localhost:5001

The CLI mode will list available fighters from the local DB and prompt you to choose or manually enter stats for Fighter 1 and Fighter 2.

## Design & Mathematical Model

This project uses Monte Carlo sampling to simulate many independent fights and estimate outcome probabilities.

Key modeling concepts:

- Win / KO rates are estimated from historical counts. Uncertainty is modeled using the binomial standard deviation:

  - For win rate p with n bouts: σ_p = sqrt(p(1 - p) / n)
  - For KO rate q with n wins: σ_q = sqrt(q(1 - q) / n)

- Physical attributes (height, reach) are modeled with small Gaussian noise: sampled ~ N(actual, σ_attr) where σ_attr is small (default 1 cm).

- Each simulation samples perturbed versions of these statistics and computes a weighted fight score for each fighter. A simple score example used in the code:

  score = 0.50 × sampled_win_rate
        + 0.25 × sampled_ko_rate
        + 0.125 × normalized_height_advantage
        + 0.125 × normalized_reach_advantage
        + N(0, 0.1)

- Outcome determination:
  - If |score1 − score2| < draw_threshold → Draw
  - Else higher score wins

- KO attribution: when a fighter wins, an independent sample using the sampled KO rate determines if the outcome is a KO.

These choices are intentionally simple and transparent; they can be extended to include weight classes, opponent-adjusted ratings, recency decay, and more advanced Bayesian updating.

## Monte Carlo & Convergence

- The law of large numbers ensures the Monte Carlo estimate converges as number of trials N increases. Typical defaults: 100k simulations for stable point estimates.
- Monte Carlo standard error for a probability p is sqrt(p(1−p)/N). Use this to build confidence intervals.

## Multiprocessing

- The simulation splits total trials into batches across available CPU cores using `multiprocessing.Pool`.
- Each worker runs `batch_size` simulations and returns counts; the main process aggregates results and computes percentages.
- This approach reduces wall-clock time approximately proportional to core count (subject to Python overhead and GIL-avoiding work in NumPy).

## File Structure

- `main.py` — main entrypoint, `BoxingDB`, simulation functions, CLI and optional Flask routes.
- `templates/` — optional web UI templates.
- `static/` — optional JS/CSS (Chart.js integration for plots in the browser).
- `requirements.txt` — dependencies.
- `test_*.py` — smoke and unit tests (if present).

## How to Use

- CLI: run `python main.py` and follow prompts to select or manually enter Fighter 1 and Fighter 2.
- Web UI: run `python main.py` and open `http://localhost:5001`. The web UI uses the local `fighter_db` selects and a simulate button.

## Limitations & Future Improvements

- Current predictive model is heuristic: weights and thresholds are hand-chosen and simplistic.
- No opponent-adjusted metrics (e.g., Elo, Glicko). Adding these would improve realism.
- No time-decay weighting for form (recent fights should often matter more).
- Expand physical modeling to account for weight class differences, age-related decline, and reach/height normalization.
- Add unit tests for statistical properties and reproducibility (set random seeds).

## Reproducibility & Testing

- To reproduce results, set the RNG seed in the simulation functions.
- A smoke test script (`smoke_test.py`) is included for quick local verification (if present).

## Explanation for Non-Technical Users

- The simulation runs many hypothetical fights with slightly varied fighter stats to see how often each fighter wins.
- The percentages reported are frequencies across simulated fights and reflect modeled uncertainty, not certainties.

## Notes & Disclaimer

This project is for educational and research use. Predictions are approximate and should not be used for betting or financial decisions.

---

