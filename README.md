# 🥊 Boxing MonteCarlo

> A sophisticated Monte Carlo simulation engine for predicting boxing match outcomes using statistical modeling and historical fighter data.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**⚠️ Educational & Research Use Only** — Not intended for betting or financial decisions.

---

## 🎯 What It Does

BoxingMonteCarlo simulates thousands of virtual fights between boxers to predict win probabilities, draw likelihood, and knockout chances. By running 100,000+ simulations with statistical variance, it provides probability distributions rather than simple predictions.

### Key Features

- **🎲 Monte Carlo Simulation** — Runs thousands of fight scenarios with statistical variation
- **💾 Local Fighter Database** — Curated stats for analysis without external API dependencies
- **⚡ Multiprocessing** — Leverages all CPU cores for fast simulation
- **🖥️ Dual Interface** — CLI for quick analysis + optional web UI for visualization
- **📊 Statistical Modeling** — Incorporates uncertainty in fighter metrics using binomial distributions

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/boxing-montecarlo.git
cd boxing-montecarlo

# Install dependencies
pip install -r requirements.txt
```

### Run Simulations

**CLI Mode** (Recommended for analysis):
```bash
python main.py
```

**Web UI Mode** (Visual interface):
```bash
python main.py
# Open http://localhost:5001 in your browser
```

---

## 📐 How It Works

### The Statistical Model

The simulation models fight outcomes using several statistical components:

#### 1. **Win Rate Uncertainty**
Fighter win rates aren't fixed values — they have statistical uncertainty based on sample size:

```
σ_winrate = √(p × (1-p) / n)
```
Where `p` is the win rate and `n` is total bouts.

#### 2. **Physical Attributes**
Height and reach are sampled with small Gaussian noise:
```
sampled_height ~ N(actual_height, 1 cm)
```

#### 3. **Fight Score Calculation**
Each simulation computes a weighted score:

```
score = 0.50 × win_rate
      + 0.25 × ko_rate  
      + 0.125 × height_advantage
      + 0.125 × reach_advantage
      + random_noise
```

#### 4. **Outcome Determination**
- **Draw**: `|score₁ - score₂| < threshold`
- **Winner**: Fighter with higher score
- **KO Check**: Independent sample based on winner's KO rate

### Convergence & Accuracy

The Monte Carlo method converges to true probabilities as simulations increase. Standard error for probability `p` with `N` simulations:

```
SE = √(p × (1-p) / N)
```

With 100,000 simulations, a 50% probability has a standard error of ±0.16%.

---

## 🏗️ Project Structure

```
boxing-montecarlo/
│
├── main.py              # Core simulation engine & entry point
├── requirements.txt     # Python dependencies
│
├── templates/           # Web UI HTML templates
├── static/             # CSS, JavaScript, Chart.js
│
└── tests/              # Unit and smoke tests
    └── test_*.py
```

---

## 💡 Usage Examples

### CLI: Select from Database
```
Available fighters:
1. Tyson Fury
2. Oleksandr Usyk
3. Canelo Alvarez
...

Select Fighter 1: 1
Select Fighter 2: 2

Running 100,000 simulations...
Results:
  Tyson Fury:     52.3% wins (8.2% by KO)
  Oleksandr Usyk: 43.1% wins (6.5% by KO)
  Draw:           4.6%
```

### CLI: Manual Input
```
Enter custom stats for Fighter 1:
  Name: Custom Fighter
  Wins: 25
  Losses: 2
  ...
```

---

## 🔬 Technical Details

### Dependencies
- **numpy** — Fast numerical operations
- **pandas** — Data handling for fighter database
- **matplotlib** — Visualization (CLI mode)
- **flask** — Optional web UI framework
- **multiprocessing** — Parallel simulation across CPU cores

### Multiprocessing Architecture
The simulation distributes work across all available CPU cores:

1. Divide total simulations into batches (one per core)
2. Each worker runs its batch independently
3. Main process aggregates results

Speedup is approximately linear with core count (subject to Python overhead).

---

## 🎓 Educational Notes

### For Non-Technical Users
Think of this as running thousands of "what-if" scenarios. Each fight is slightly different because fighters don't perform exactly the same every time. The percentages show how often each fighter won across all these virtual matches.

### Statistical Concepts Demonstrated
- **Monte Carlo Integration** — Estimating probabilities through random sampling
- **Law of Large Numbers** — Convergence with sample size
- **Confidence Intervals** — Quantifying uncertainty
- **Multivariate Modeling** — Combining multiple attributes
- **Binomial Distributions** — Modeling win/loss records

---

## 🚧 Current Limitations

The model uses simplified heuristics and could be improved with:

- **Opponent-Adjusted Ratings** — Elo/Glicko systems for strength of schedule
- **Temporal Weighting** — Recent fights should matter more
- **Weight Class Modeling** — Better handling of size differences
- **Age/Career Arc** — Modeling prime years and decline
- **Style Matchups** — Counter-puncher vs. aggressive fighter dynamics
- **Injury History** — Durability and recovery factors

---

## 🔮 Future Roadmap

- [ ] Bayesian parameter estimation for fighter attributes
- [ ] Historical validation against actual fight outcomes
- [ ] Advanced physical models (punch power, stamina, defense)
- [ ] Web scraping pipeline for automatic database updates
- [ ] Interactive visualizations with confidence intervals
- [ ] REST API for programmatic access
- [ ] Round-by-round simulation mode

---

## 🧪 Testing & Reproducibility

### Running Tests
```bash
python -m pytest tests/
```

### Reproducible Results
Set random seed for deterministic output:
```python
import numpy as np
np.random.seed(42)
```

---

## 📝 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions welcome! Areas needing help:

- Expanding the fighter database
- Improving the statistical model
- Adding test coverage
- UI/UX enhancements

Please open an issue before starting major work.

---

## ⚖️ Disclaimer

**This software is for educational and research purposes only.** Predictions are statistical estimates based on simplified models and historical data. They should not be used for:

- Gambling or betting decisions
- Financial investments
- Professional sports analysis without expert review

Boxing is inherently unpredictable. No statistical model can account for all factors that determine fight outcomes.

---

## 📚 References & Further Reading

- [Monte Carlo Methods in Practice](https://en.wikipedia.org/wiki/Monte_Carlo_method)
- [Elo Rating System](https://en.wikipedia.org/wiki/Elo_rating_system)
- [Statistical Modeling in Sports](https://www.stat.berkeley.edu/~aldous/157/Papers/ranking.pdf)

---

<div align="center">

**Built with ❤️ for boxing stats enthusiasts**

[Report Bug](https://github.com/yourusername/boxing-montecarlo/issues) · [Request Feature](https://github.com/yourusername/boxing-montecarlo/issues)

</div>
