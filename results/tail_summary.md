# Crypto Risk Lab - Part 2: tail risk, VaR and Expected Shortfall

Generated 2026-10-16 22:03 | data: Binance daily candles | window 500 days, EWMA lambda 0.94, tail refit every 20 days

## Tail shape

| asset | days | first | hill_alpha_left | gpd_xi_median | excess_kurtosis | down_beyond_3sd | down_beyond_4sd | down_beyond_5sd |
|---|---|---|---|---|---|---|---|---|
| BTC | 2844 | 2019-01-02 | 2.58 | 0.11 | 23.3 | 29 (normal: 3.84) | 14 (normal: 0.09) | 5 (normal: 0.0) |
| ETH | 2844 | 2019-01-02 | 2.62 | 0.069 | 16.7 | 31 (normal: 3.84) | 9 (normal: 0.09) | 4 (normal: 0.0) |
| Basket (30 coins) | 2113 | 2021-01-02 | 2.69 | -0.031 | 7.9 | 27 (normal: 2.85) | 7 (normal: 0.07) | 2 (normal: 0.0) |

_hill_alpha_left: Hill tail index on the 5% largest losses (below 4 = infinite kurtosis). Counts use returns scaled by EWMA volatility known the day before._

## BTC - 99.0% VaR / ES

| model | days | breaches | expected | ratio | kupiec_p | christoffersen_p | back_to_back | es_realized_over_predicted | es_test_t | avg_var | basel_green | basel_yellow | basel_red | basel_worst_window |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | 2344 | 35 | 23.4 | 1.49 | 0.0253 | 0.5507 | 1 | 1.14 | 3.11 | 7.32 | 56.3 | 43.7 | 0.0 | 8 |
| historical | 2344 | 22 | 23.4 | 0.94 | 0.7626 | 0.2022 | 1 | 0.85 | -1.98 | 8.52 | 93.7 | 6.3 | 0.0 | 6 |
| ewma_normal | 2344 | 49 | 23.4 | 2.09 | 0.0 | 0.98 | 1 | 1.22 | 4.36 | 6.56 | 23.3 | 73.1 | 3.6 | 10 |
| ewma_t | 2344 | 37 | 23.4 | 1.58 | 0.0094 | 0.615 | 1 | 0.84 | -3.27 | 7.7 | 57.4 | 42.6 | 0.0 | 8 |
| filtered_hs | 2344 | 29 | 23.4 | 1.24 | 0.2657 | 0.3722 | 1 | 0.86 | -1.19 | 8.38 | 81.6 | 18.4 | 0.0 | 7 |
| evt | 2344 | 27 | 23.4 | 1.15 | 0.4706 | 0.3189 | 1 | 0.91 | -0.42 | 8.47 | 75.8 | 24.2 | 0.0 | 7 |

## BTC - 97.5% VaR / ES

| model | days | breaches | expected | ratio | kupiec_p | christoffersen_p | back_to_back | es_realized_over_predicted | es_test_t | avg_var |
|---|---|---|---|---|---|---|---|---|---|---|
| normal | 2344 | 58 | 58.6 | 0.99 | 0.9366 | 0.6939 | 1 | 1.15 | 3.64 | 6.15 |
| historical | 2344 | 58 | 58.6 | 0.99 | 0.9366 | 0.6939 | 1 | 0.91 | -1.95 | 6.23 |
| ewma_normal | 2344 | 74 | 58.6 | 1.26 | 0.0501 | 0.1151 | 5 | 1.21 | 4.65 | 5.53 |
| ewma_t | 2344 | 85 | 58.6 | 1.45 | 0.0011 | 0.1238 | 6 | 0.91 | -2.14 | 5.38 |
| filtered_hs | 2344 | 61 | 58.6 | 1.04 | 0.7524 | 0.7466 | 2 | 0.94 | -0.39 | 5.91 |
| evt | 2344 | 59 | 58.6 | 1.01 | 0.9578 | 0.6803 | 2 | 0.94 | -0.43 | 6.04 |

## ETH - 99.0% VaR / ES

| model | days | breaches | expected | ratio | kupiec_p | christoffersen_p | back_to_back | es_realized_over_predicted | es_test_t | avg_var | basel_green | basel_yellow | basel_red | basel_worst_window |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | 2344 | 40 | 23.4 | 1.71 | 0.0018 | 0.0045 | 4 | 1.18 | 3.91 | 9.73 | 59.8 | 27.7 | 12.5 | 13 |
| historical | 2344 | 33 | 23.4 | 1.41 | 0.0615 | 0.0106 | 3 | 0.88 | -2.4 | 11.22 | 71.4 | 28.2 | 0.4 | 11 |
| ewma_normal | 2344 | 49 | 23.4 | 2.09 | 0.0 | 0.1028 | 3 | 1.18 | 4.17 | 8.84 | 23.6 | 73.8 | 2.5 | 10 |
| ewma_t | 2344 | 27 | 23.4 | 1.15 | 0.4706 | 0.3189 | 1 | 0.89 | -2.13 | 10.65 | 87.4 | 12.6 | 0.0 | 6 |
| filtered_hs | 2344 | 29 | 23.4 | 1.24 | 0.2657 | 0.0518 | 2 | 0.91 | -0.95 | 10.91 | 74.8 | 25.2 | 0.0 | 7 |
| evt | 2344 | 25 | 23.4 | 1.07 | 0.7487 | 0.2693 | 1 | 0.98 | 0.26 | 11.43 | 88.9 | 11.1 | 0.0 | 6 |

## ETH - 97.5% VaR / ES

| model | days | breaches | expected | ratio | kupiec_p | christoffersen_p | back_to_back | es_realized_over_predicted | es_test_t | avg_var |
|---|---|---|---|---|---|---|---|---|---|---|
| normal | 2344 | 64 | 58.6 | 1.09 | 0.4814 | 0.0017 | 7 | 1.18 | 4.13 | 8.18 |
| historical | 2344 | 59 | 58.6 | 1.01 | 0.9578 | 0.0185 | 5 | 0.97 | -0.63 | 8.27 |
| ewma_normal | 2344 | 78 | 58.6 | 1.33 | 0.0145 | 0.8002 | 3 | 1.19 | 4.73 | 7.45 |
| ewma_t | 2344 | 75 | 58.6 | 1.28 | 0.0374 | 0.6999 | 3 | 0.93 | -2.15 | 7.64 |
| filtered_hs | 2344 | 59 | 58.6 | 1.01 | 0.9578 | 0.2599 | 3 | 0.98 | -0.01 | 8.27 |
| evt | 2344 | 60 | 58.6 | 1.02 | 0.8536 | 0.2809 | 3 | 0.96 | -0.55 | 8.34 |

## Basket (30 coins) - 99.0% VaR / ES

| model | days | breaches | expected | ratio | kupiec_p | christoffersen_p | back_to_back | es_realized_over_predicted | es_test_t | avg_var | basel_green | basel_yellow | basel_red | basel_worst_window |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | 1613 | 26 | 16.1 | 1.61 | 0.0233 | 0.0073 | 3 | 1.24 | 2.9 | 9.17 | 57.3 | 30.5 | 12.2 | 11 |
| historical | 1613 | 15 | 16.1 | 0.93 | 0.7748 | 0.0065 | 2 | 1.02 | 0.11 | 11.19 | 85.0 | 15.0 | 0.0 | 7 |
| ewma_normal | 1613 | 35 | 16.1 | 2.17 | 0.0 | 0.2234 | 2 | 1.23 | 3.63 | 8.16 | 19.1 | 80.9 | 0.0 | 9 |
| ewma_t | 1613 | 23 | 16.1 | 1.43 | 0.1061 | 0.3361 | 1 | 1.0 | 0.01 | 9.74 | 72.4 | 27.6 | 0.0 | 6 |
| filtered_hs | 1613 | 16 | 16.1 | 0.99 | 0.974 | 0.1484 | 1 | 1.06 | 0.54 | 11.12 | 90.6 | 9.4 | 0.0 | 6 |
| evt | 1613 | 18 | 16.1 | 1.12 | 0.6459 | 0.1944 | 1 | 1.05 | 0.51 | 10.96 | 86.2 | 13.8 | 0.0 | 6 |

## Basket (30 coins) - 97.5% VaR / ES

| model | days | breaches | expected | ratio | kupiec_p | christoffersen_p | back_to_back | es_realized_over_predicted | es_test_t | avg_var |
|---|---|---|---|---|---|---|---|---|---|---|
| normal | 1613 | 41 | 40.3 | 1.02 | 0.9145 | 0.0214 | 4 | 1.23 | 3.15 | 7.73 |
| historical | 1613 | 31 | 40.3 | 0.77 | 0.1213 | 0.0215 | 3 | 1.04 | 0.37 | 8.28 |
| ewma_normal | 1613 | 62 | 40.3 | 1.54 | 0.0013 | 0.0102 | 7 | 1.2 | 3.76 | 6.87 |
| ewma_t | 1613 | 54 | 40.3 | 1.34 | 0.038 | 0.0096 | 6 | 1.01 | -0.03 | 7.33 |
| filtered_hs | 1613 | 41 | 40.3 | 1.02 | 0.9145 | 0.1053 | 3 | 0.99 | -0.17 | 8.11 |
| evt | 1613 | 39 | 40.3 | 0.97 | 0.8318 | 0.0804 | 3 | 1.01 | 0.04 | 8.34 |

_kupiec_p < 0.05: wrong number of breaches. christoffersen_p < 0.05: breaches cluster. es_realized_over_predicted > 1: losses beyond VaR worse than forecast; es_test_t > 2 is significant. basel_*: % of rolling 250-day windows in each zone._
