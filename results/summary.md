# Crypto Risk Lab - results

Generated 2026-10-16 21:07 | data: Binance daily candles; Deribit DVOL
## Part 1 - Volatility

### Estimators (BTC, 30-day window)
| estimator | mean_level | bias_vs_future | rmse | corr_with_future | noise_ratio |
|---|---|---|---|---|---|
| close_to_close | 56.7 | 0.09 | 28.68 | 0.355 | 1.0 |
| parkinson | 59.9 | 3.22 | 27.65 | 0.409 | 0.69 |
| garman_klass | 60.9 | 4.21 | 27.78 | 0.42 | 0.65 |
| rogers_satchell | 61.3 | 4.61 | 28.28 | 0.42 | 0.7 |
| yang_zhang | 60.8 | 4.08 | 28.07 | 0.416 | 0.69 |

_bias/rmse/corr measured against realized close-to-close volatility of the NEXT 30 days, 93 non-overlapping blocks. noise_ratio = day-to-day jitter vs close-to-close._

### Volatility clustering (BTC, 2844 days)

- autocorrelation of returns at lag 1: -0.069
- autocorrelation of absolute returns: lag 1 = 0.167, lag 30 = 0.038
- Ljung-Box Q(20) on squared returns = 65.1 (p = 1.12e-06)

### GARCH(1,1) walk-forward, BTC

2114 out-of-sample days, 71 refits. Latest fit: alpha 0.126, beta 0.834, persistence 0.9606, half-life of a volatility shock 17.3 days.

| proxy | model | qlike | mse |
|---|---|---|---|
| r2 | garch | 3.0802 | 469.5637 |
| r2 | ewma | 3.0824 | 462.3743 |
| r2 | rolling30 | 3.1551 | 470.1048 |
| gk | garch | 3.1734 | 460.9672 |
| gk | ewma | 3.2038 | 473.9787 |
| gk | rolling30 | 3.2877 | 494.5491 |

Diebold-Mariano t-stats (negative = GARCH better): {'garch_vs_ewma_r2': -0.07, 'garch_vs_rolling30_r2': -1.55, 'garch_vs_ewma_gk': -0.99, 'garch_vs_rolling30_gk': -2.53}

### GARCH(1,1) walk-forward, ETH

2114 out-of-sample days, 71 refits. Latest fit: alpha 0.082, beta 0.886, persistence 0.9679, half-life of a volatility shock 21.2 days.

| proxy | model | qlike | mse |
|---|---|---|---|
| r2 | garch | 3.6644 | 1892.4302 |
| r2 | ewma | 3.6977 | 1905.7466 |
| r2 | rolling30 | 3.7693 | 1964.5398 |
| gk | garch | 3.7114 | 1807.1041 |
| gk | ewma | 3.7543 | 1893.4788 |
| gk | rolling30 | 3.8715 | 1996.0658 |

Diebold-Mariano t-stats (negative = GARCH better): {'garch_vs_ewma_r2': -0.91, 'garch_vs_rolling30_r2': -2.09, 'garch_vs_ewma_gk': -1.39, 'garch_vs_rolling30_gk': -2.37}

### Volatility by coin (full-sample GARCH(1,1) with Student-t errors)

| coin | days | ann_vol_full | ann_vol_last_365 | alpha | beta | persistence | half_life_days | t_dof | excess_kurtosis |
|---|---|---|---|---|---|---|---|---|---|
| AXS | 2171 | 130.5 | 113.1 | 0.111 | 0.875 | 0.9862 | 50.0 | 3.6 | 9.4 |
| FIL | 2191 | 111.9 | 111.7 | 0.186 | 0.713 | 0.899 | 6.5 | 3.3 | 13.1 |
| NEAR | 2192 | 121.0 | 106.1 | 0.078 | 0.921 | 0.9986 | 481.2 | 4.4 | 4.5 |
| UNI | 2219 | 114.2 | 95.5 | 0.03 | 0.966 | 0.9962 | 181.5 | 3.8 | 13.5 |
| SAND | 2253 | 128.3 | 94.5 | 0.073 | 0.912 | 0.9853 | 46.9 | 3.6 | 14.0 |
| CHZ | 2596 | 121.5 | 86.5 | 0.17 | 0.776 | 0.9467 | 12.6 | 3.8 | 19.4 |
| SNX | 2289 | 122.3 | 86.1 | 0.101 | 0.873 | 0.974 | 26.3 | 5.6 | 7.2 |
| AAVE | 2191 | 108.4 | 85.9 | 0.121 | 0.847 | 0.9685 | 21.7 | 5.2 | 3.7 |
| CRV | 2252 | 134.0 | 84.2 | 0.099 | 0.892 | 0.9903 | 70.9 | 4.4 | 6.6 |
| DOT | 2249 | 100.2 | 81.7 | 0.074 | 0.916 | 0.99 | 69.2 | 4.2 | 9.8 |
| BCH | 2513 | 96.1 | 77.4 | 0.103 | 0.865 | 0.9682 | 21.5 | 3.1 | 19.8 |
| XLM | 2844 | 96.8 | 76.2 | 0.16 | 0.816 | 0.9764 | 29.0 | 3.6 | 18.6 |
| ADA | 2844 | 97.1 | 75.3 | 0.17 | 0.764 | 0.934 | 10.2 | 4.0 | 11.6 |
| ALGO | 2672 | 110.7 | 75.0 | 0.114 | 0.849 | 0.9624 | 18.1 | 4.9 | 12.6 |
| AVAX | 2214 | 112.9 | 72.7 | 0.1 | 0.886 | 0.9861 | 49.5 | 4.5 | 8.8 |
| VET | 2844 | 106.2 | 72.5 | 0.107 | 0.879 | 0.9858 | 48.6 | 4.5 | 11.6 |
| MANA | 2261 | 118.4 | 72.1 | 0.108 | 0.866 | 0.9743 | 26.6 | 4.0 | 29.3 |
| COMP | 2303 | 105.1 | 71.8 | 0.14 | 0.847 | 0.9871 | 53.4 | 3.9 | 4.0 |
| HBAR | 2573 | 115.5 | 69.9 | 0.191 | 0.78 | 0.9707 | 23.3 | 4.0 | 23.4 |
| ATOM | 2726 | 106.1 | 68.1 | 0.107 | 0.879 | 0.9859 | 48.8 | 4.8 | 11.0 |
| LINK | 2829 | 106.7 | 67.2 | 0.095 | 0.877 | 0.972 | 24.4 | 5.1 | 12.4 |
| DOGE | 2659 | 125.2 | 66.5 | 0.268 | 0.732 | 0.9995 | n/a (near 1) | 3.1 | 143.4 |
| ETC | 2844 | 97.9 | 65.8 | 0.214 | 0.73 | 0.9449 | 12.2 | 3.0 | 13.4 |
| XRP | 2844 | 96.3 | 64.4 | 0.235 | 0.761 | 0.9954 | 151.2 | 2.9 | 20.6 |
| SOL | 2256 | 113.3 | 64.1 | 0.121 | 0.86 | 0.9806 | 35.4 | 4.9 | 8.4 |
| ETH | 2844 | 81.7 | 61.1 | 0.105 | 0.892 | 0.9976 | 282.7 | 3.2 | 16.7 |
| LTC | 2844 | 88.3 | 57.6 | 0.086 | 0.906 | 0.9914 | 80.5 | 3.3 | 11.2 |
| BNB | 2844 | 82.1 | 45.5 | 0.134 | 0.866 | 0.9995 | n/a (near 1) | 3.6 | 27.4 |
| BTC | 2844 | 62.0 | 44.1 | 0.07 | 0.929 | 0.9995 | n/a (near 1) | 3.0 | 23.3 |
| TRX | 2844 | 82.1 | 23.3 | 0.154 | 0.846 | 0.9995 | n/a (near 1) | 3.6 | 39.4 |

### Asymmetry (BTC)

Next-5-day vol / previous-30-day vol after big DOWN days (157): 1.18; after big UP days (204): 1.044; Welch t = 1.62

### Implied (DVOL) vs realized next 30 days (BTC, 2002 days)

- mean DVOL 60.0, mean realized 51.6, mean premium 8.41 vol points (Newey-West t 5.43)
- implied above realized on 71.7% of days; worst -45.2
- by year: {2021: {'mean': 18.0, 'days': 283}, 2022: {'mean': 12.2, 'days': 365}, 2023: {'mean': 6.6, 'days': 365}, 2024: {'mean': 7.2, 'days': 366}, 2025: {'mean': 6.4, 'days': 365}, 2026: {'mean': -0.4, 'days': 258}}

## Part 3 - Correlation and market structure

Panel: 30 coins with full history, 2021-01-02 to 2026-10-15 (2113 days): BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, LINK, DOT, TRX, LTC, BCH, UNI, ATOM, XLM, ETC, FIL, NEAR, AAVE, ALGO, HBAR, VET, SAND, MANA, AXS, CRV, SNX, COMP, CHZ

### PCA (full sample)

PC1 61.0%, PC2 3.6%, PC3 3.0% of variance. PC1 loadings range 0.139 to 0.205 (equal weight would be 0.183).

### Rolling 90-day structure

- effective number of bets (equal weight, 30 coins): median 1.46, min 1.23, max 3.38
- PC1 share median 70.5%, average pairwise correlation median 0.68

Around stress events:

| event | date | btc_move_3d_pct | effective_bets_before | effective_bets_after | pc1_share_before | pc1_share_after |
|---|---|---|---|---|---|---|
| May 2021 crash | 2021-05-19 | -14.0 | 3.18 | 1.53 | 38.6 | 68.2 |
| LUNA | 2022-05-09 | -15.7 | 1.4 | 1.25 | 73.0 | 80.6 |
| FTX | 2022-11-08 | -15.7 | 1.47 | 1.29 | 70.4 | 79.1 |
| Aug 2024 unwind | 2024-08-05 | -5.3 | 1.45 | 1.4 | 70.8 | 72.1 |
| Oct 2025 liquidations | 2025-10-10 | -5.7 | 1.34 | 1.23 | 74.5 | 82.0 |

### Beta and R^2 to BTC

Median beta 1.18, median R^2 0.39 (lowest TRX 0.271, highest ETH 0.677).

| coin | beta_full | beta_last_365 | r2_full | r2_last_365 |
|---|---|---|---|---|
| ETH | 1.11 | 1.26 | 0.677 | 0.822 |
| LTC | 1.06 | 0.94 | 0.516 | 0.513 |
| LINK | 1.22 | 1.25 | 0.498 | 0.673 |
| VET | 1.25 | 1.18 | 0.495 | 0.512 |
| DOT | 1.18 | 1.15 | 0.487 | 0.387 |
| BCH | 1.13 | 1.1 | 0.478 | 0.396 |
| ADA | 1.14 | 1.37 | 0.469 | 0.638 |
| BNB | 0.91 | 0.84 | 0.447 | 0.661 |
| ETC | 1.14 | 1.1 | 0.439 | 0.544 |
| ALGO | 1.16 | 1.07 | 0.427 | 0.395 |
| AAVE | 1.2 | 1.37 | 0.418 | 0.495 |
| AVAX | 1.25 | 1.19 | 0.404 | 0.523 |
| COMP | 1.15 | 0.94 | 0.398 | 0.331 |
| SOL | 1.2 | 1.26 | 0.397 | 0.756 |
| UNI | 1.18 | 1.34 | 0.39 | 0.381 |
| XRP | 1.04 | 1.26 | 0.384 | 0.748 |
| XLM | 1.03 | 1.06 | 0.384 | 0.38 |
| ATOM | 1.09 | 0.84 | 0.375 | 0.295 |
| FIL | 1.18 | 1.23 | 0.374 | 0.235 |
| SNX | 1.28 | 1.24 | 0.373 | 0.401 |
| CRV | 1.32 | 1.21 | 0.367 | 0.402 |
| NEAR | 1.25 | 1.27 | 0.359 | 0.277 |
| HBAR | 1.11 | 1.05 | 0.34 | 0.438 |
| MANA | 1.2 | 1.09 | 0.337 | 0.441 |
| AXS | 1.26 | 1.1 | 0.326 | 0.183 |
| CHZ | 1.13 | 1.01 | 0.3 | 0.264 |
| SAND | 1.21 | 1.24 | 0.296 | 0.334 |
| DOGE | 1.27 | 1.2 | 0.294 | 0.638 |
| TRX | 0.68 | 0.21 | 0.271 | 0.156 |

### Exceedance correlation with BTC

At the 10% tail: DOWN {'empirical': 0.586, 'normal': 0.257}, UP {'empirical': 0.184, 'normal': 0.259}; down minus up = 0.402 (block-bootstrap 95% CI [0.221, 0.505], share of resamples above 0: 1.0)

| q | empirical | normal |
|---|---|---|
| 0.05 | 0.566 | 0.227 |
| 0.1 | 0.586 | 0.257 |
| 0.15 | 0.618 | 0.28 |
| 0.2 | 0.644 | 0.298 |
| 0.25 | 0.663 | 0.317 |
| 0.3 | 0.674 | 0.334 |
| 0.35 | 0.681 | 0.349 |
| 0.4 | 0.691 | 0.366 |
| 0.45 | 0.699 | 0.38 |
| 0.55 | 0.401 | 0.381 |
| 0.6 | 0.383 | 0.366 |
| 0.65 | 0.373 | 0.35 |
| 0.7 | 0.346 | 0.334 |
| 0.75 | 0.317 | 0.317 |
| 0.8 | 0.287 | 0.3 |
| 0.85 | 0.251 | 0.281 |
| 0.9 | 0.184 | 0.259 |
| 0.95 | 0.095 | 0.224 |

### Last 365 days

Average pairwise correlation 0.596 (min 0.174, max 0.907)
