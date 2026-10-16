# Crypto Risk Lab

How risky is the crypto market really, where does that risk come from, and what happens to it in a crash?

This project measures **volatility** and **correlation structure** across 30 major coins, using public data only (Binance daily candles since 2019, Deribit's DVOL implied-volatility index since 2021). Every forecast is made walk-forward, using only data available at the time.

## Key findings

| # | Finding | Evidence |
|---|---|---|
| 1 | **A basket of 30 coins behaves like about 1.5 independent bets.** Holding many coins is not diversification. | Effective number of bets (diversification ratio²), median 1.46 over rolling 90-day windows; one common factor explains 61% of all variance |
| 2 | **Correlation rises in sell-offs and falls in rallies.** On the worst 10% of days, alts move with BTC far more than a normal model predicts. | Exceedance correlation 0.59 on down days vs 0.26 expected; 0.18 on up days |
| 3 | **The direction of BTC is unpredictable, the size of its moves is not.** Volatility clusters for weeks. | Autocorrelation of returns −0.07, of absolute returns +0.17; Ljung-Box p ≈ 10⁻⁶ |
| 4 | **GARCH beats a simple 30-day window, but not a simple EWMA.** | Diebold-Mariano t (QLIKE, range-based proxy) = −2.5 (BTC) and −2.4 (ETH) vs rolling window; −1.0 and −1.4 vs EWMA |
| 5 | **Options have usually priced more volatility than was delivered, but that premium is fading.** | DVOL above next-30-day realized by 8.4 vol points on average (Newey-West t 5.4); 18 points in 2021, 6-7 in 2023-2025, about zero in 2026 |
| 6 | **"High beta" does not mean "mostly BTC".** Alts move about 1.2× BTC, yet BTC explains only about 40% of their daily variance. | Median beta 1.18, median R² 0.39 (ETH 0.68, TRX 0.27) |

## 1. Volatility

### Volatility clusters

![Volatility clustering](results/02_btc_volatility_clustering.png)

Returns themselves show almost no memory, but the **size** of returns does: a large move today makes another large move more likely for weeks. This is the basis for every volatility model below, and the reason position sizing should react to recent volatility.

### Which estimator to use

![Volatility estimators](results/01_btc_vol_estimators.png)

| Estimator | Uses | Noise vs close-to-close | Correlation with next month |
|---|---|---|---|
| Close-to-close | closes | 1.00 | 0.36 |
| Parkinson | high, low | 0.69 | 0.41 |
| Garman-Klass | open, high, low, close | 0.65 | 0.42 |
| Yang-Zhang | open, high, low, close | 0.69 | 0.42 |

Range-based estimators use the whole day's path, not just one price, so they are about 30% less noisy and slightly better at forecasting next month. They also run 3-5 vol points higher than close-to-close: crypto often reverses within the day, so the close understates how much the price actually travelled.

### Forecasting tomorrow's volatility

![GARCH forecast](results/03_btc_garch_forecast.png)

GARCH(1,1) was refitted every 30 days on past data only (71 refits, 2,114 out-of-sample days) and compared with EWMA (λ = 0.94, the RiskMetrics standard) and a 30-day rolling window. Losses use QLIKE, which ranks models correctly even with a noisy volatility proxy (Patton, 2011).

- GARCH is **significantly better than the rolling window** for both BTC and ETH.
- GARCH is **not significantly better than EWMA**. In practice, the simpler model is good enough.
- BTC volatility shocks have a half-life of about 17 days (persistence 0.96).

### Implied vs realized

![Implied vs realized](results/04_btc_implied_vs_realized.png)

The gap between DVOL and the volatility that followed is the **volatility risk premium**: what option buyers pay for protection. It was positive on 72% of days, but the left tail is severe (worst −45 vol points), it has shrunk year after year, and in 2026 it has been about zero.

## 2. Correlation and market structure

### How many bets are you really holding?

![Effective bets](results/05_effective_bets.png)

An equal-weight basket of 30 coins behaves like 1.2 to 2 independent positions most of the time. Diversification is lowest right after stress events (LUNA, FTX, the October 2025 liquidations), exactly when it would be needed.

![PCA](results/06_pca_market_factor.png)

One common factor ("the crypto market") explains 61% of the variance of all 30 coins over the full sample, and 70% in a typical 90-day window. After stress events it rises to around 80%.

### Correlation in the tails

![Exceedance correlation](results/08_exceedance_correlation.png)

Exceedance correlation (Longin and Solnik, 2001) measures correlation only on days when both coins are beyond a threshold. The grey line is what a normal distribution with the same overall correlation would give. On the downside, crypto correlations are more than twice that benchmark; on the upside they are at or below it. **Correlation is asymmetric: it is highest exactly when prices are falling.**

### Market risk vs coin-specific risk

![Beta and R2](results/07_beta_r2_to_btc.png)

![Correlation map](results/09_correlation_heatmap.png)

## What this means for risk management

1. **Count bets, not coins.** Risk limits should be set on exposure to the common factor, not on the number of positions.
2. **Use stress correlations, not average correlations.** A portfolio sized with average correlations will be under-hedged in a sell-off.
3. **Size positions by volatility, and update it.** Volatility is persistent and forecastable; a simple EWMA captures most of what is available.
4. **Normal-distribution risk models understate crypto tail risk.** Fat tails (excess kurtosis above 10 for most coins) and asymmetric correlation both work against them.

## Method notes and limits

- Daily data; all statistics on log returns, annualized with 365 days (crypto trades every day).
- Walk-forward forecasts only; t-stats use Newey-West standard errors where observations overlap.
- **Survivorship bias:** only coins still listed on Binance today are included.
- DVOL data starts in March 2021; the 2026 figures cover a partial year.
- Effective bets use the diversification ratio squared (Choueifaty and Coignard, 2008), an approximation.

## Run it

```bash
pip install -r requirements.txt
python crypto_risk_lab.py               # downloads public data, writes charts and summary to results/
python crypto_risk_lab.py --synthetic   # quick check on fake data
```

All numbers in this README come from [`results/summary.md`](results/summary.md), which the script regenerates on every run.

---
*Code written with AI assistance. Research design, interpretation and conclusions are my own.*
