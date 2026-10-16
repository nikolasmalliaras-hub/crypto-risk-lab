#!/usr/bin/env python3
"""
Crypto Risk Lab - Part 1 (volatility) and Part 3 (correlation and market structure).

Public data only: Binance daily candles (no account, no API key) and Deribit's public DVOL index.
Everything is computed walk-forward / from past data only where a forecast is involved.

Usage:
  pip install -r requirements.txt
  python crypto_risk_lab.py                 # real data (first run downloads ~2-4 minutes)
  python crypto_risk_lab.py --synthetic     # fake data, only checks that the code runs

Output: a folder "results" with charts (PNG), summary.md (all tables and key numbers) and summary.json.
"""
import argparse, json, math, os, time, urllib.request, urllib.parse, warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------- settings
UNIVERSE = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT", "TRX", "LTC", "BCH", "UNI",
            "ATOM", "XLM", "ETC", "FIL", "NEAR", "AAVE", "ALGO", "HBAR", "VET", "SAND", "MANA", "AXS", "CRV",
            "SNX", "COMP", "CHZ"]
BIN_HOSTS = ["https://data-api.binance.vision", "https://api.binance.com"]
DERIBIT = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
ANN = 365.0                                     # crypto trades every day
EVENTS = [("2021-05-19", "May 2021 crash"), ("2022-05-09", "LUNA"), ("2022-11-08", "FTX"),
          ("2024-08-05", "Aug 2024 unwind"), ("2025-10-10", "Oct 2025 liquidations")]

# chart style (validated reference palette, light surface)
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
NEUTRAL = "#c3c2b7"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlecolor": INK,
})


# ---------------------------------------------------------------- data
def get_json(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (400, 404) or k == tries - 1:
                raise
            time.sleep(4 * (k + 1) * (6 if code in (418, 429) else 1))


def fetch_daily(coin, start, cache):
    """Daily OHLCV for COINUSDT from Binance, cached as CSV. The still-forming candle is dropped."""
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, f"{coin}_1d.csv")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 12 * 3600:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    cur, rows, err = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000), [], None
    while True:
        ch = None
        for host in BIN_HOSTS:
            try:
                ch = get_json(f"{host}/api/v3/klines?symbol={coin}USDT&interval=1d&limit=1000&startTime={cur}")
                break
            except Exception as e:
                err = e
        if ch is None:
            raise err
        if not ch:
            break
        rows += ch
        if len(ch) < 1000:
            break
        cur = ch[-1][0] + 86_400_000
        time.sleep(0.3)
    if not rows:
        raise ValueError("no data")
    df = pd.DataFrame([[float(x) for x in r[1:6]] for r in rows], columns=["open", "high", "low", "close", "volume"],
                      index=pd.to_datetime([r[0] for r in rows], unit="ms"))
    df = df[~df.index.duplicated()].sort_index().iloc[:-1]
    df.to_csv(path)
    return df


def fetch_dvol(currency, start, cache):
    """Deribit DVOL (30-day implied volatility index, annualized %) daily closes."""
    path = os.path.join(cache, f"DVOL_{currency}.csv")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 12 * 3600:
        return pd.read_csv(path, index_col=0, parse_dates=True)["dvol"]
    t0 = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    end, rows = int(time.time() * 1000), []
    while end > t0:
        q = urllib.parse.urlencode(dict(currency=currency, start_timestamp=t0, end_timestamp=end, resolution="1D"))
        res = get_json(f"{DERIBIT}?{q}")["result"]
        data = res.get("data", [])
        if not data:
            break
        rows += data
        cont = res.get("continuation")
        if not cont or cont >= end:
            break
        end = cont
        time.sleep(0.3)
    s = pd.Series({pd.to_datetime(r[0], unit="ms"): float(r[4]) for r in rows}, name="dvol").sort_index()
    s.index = s.index.normalize()
    s = s[~s.index.duplicated()]
    s.to_frame().to_csv(path)
    return s


def synthetic_market(n_days=2600, n_coins=24, seed=7):
    """Fake but realistic-looking data: one common factor with GARCH volatility, fat tails, intraday paths for OHLC."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=n_days, freq="D")
    names = UNIVERSE[:n_coins]
    w, a, b = 0.15, 0.10, 0.86
    h, f = np.empty(n_days), np.empty(n_days)
    h[0] = w / (1 - a - b)
    for t in range(n_days):
        if t:
            h[t] = w + a * f[t - 1] ** 2 + b * h[t - 1]
        f[t] = math.sqrt(h[t]) * rng.standard_t(4) / math.sqrt(2)
    out = {}
    for i, c in enumerate(names):
        beta = 1.0 if i == 0 else rng.uniform(0.8, 1.5)
        idio = rng.uniform(0.6, 1.6)
        crash = (f < np.quantile(f, 0.05)) * rng.uniform(0.2, 0.6)           # extra co-movement in crashes
        r = (beta + crash) * f + idio * rng.standard_t(5, n_days) / math.sqrt(5 / 3)
        r = r / 100
        start = 0 if i < 8 else rng.integers(200, 700)
        steps = rng.standard_normal((n_days, 24)) * (np.abs(r)[:, None] + 0.01) / math.sqrt(24)
        steps += (r[:, None] - steps.sum(1, keepdims=True)) / 24
        paths = np.cumsum(steps, 1)
        lvl = np.concatenate([[0], np.cumsum(r)[:-1]]) + math.log(100 * (i + 1))
        o, c_ = np.exp(lvl), np.exp(lvl + paths[:, -1])
        hi = np.exp(lvl + np.maximum(paths.max(1), 0))
        lo = np.exp(lvl + np.minimum(paths.min(1), 0))
        df = pd.DataFrame(dict(open=o, high=hi, low=lo, close=c_, volume=1.0), index=idx).iloc[start:]
        out[c] = df
    rv = np.sqrt(pd.Series(np.log(out["BTC"]["close"]).diff() ** 2).rolling(30).mean() * ANN) * 100
    dvol = (rv.shift(-30) * 0.9 + 8 + rng.normal(0, 4, len(rv))).dropna()
    dvol.name = "dvol"
    return out, dvol


# ---------------------------------------------------------------- helpers
def nw_tstat(x, lags=None):
    """t-stat of the mean with Newey-West (HAC) standard errors - needed when observations overlap or cluster."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 10:
        return float("nan")
    lags = int(4 * (n / 100) ** (2 / 9)) if lags is None else lags
    u = x - x.mean()
    s = u @ u / n
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * (u[L:] @ u[:-L]) / n
    return float(x.mean() / math.sqrt(s / n)) if s > 0 else float("nan")


def daily_variance_estimators(df):
    """Per-day variance contributions for the range-based estimators (all in log-return units)."""
    o, h, l, c = (np.log(df[k]) for k in ("open", "high", "low", "close"))
    hl, co = h - l, c - o
    return pd.DataFrame({
        "close_to_close": np.log(df["close"]).diff() ** 2,
        "parkinson": hl ** 2 / (4 * math.log(2)),
        "garman_klass": 0.5 * hl ** 2 - (2 * math.log(2) - 1) * co ** 2,
        "rogers_satchell": (h - c) * (h - o) + (l - c) * (l - o),
    })


def rolling_vols(df, n=30):
    """Annualized rolling volatility (%) by estimator, including Yang-Zhang."""
    d = daily_variance_estimators(df)
    r = np.log(df["close"]).diff()
    out = pd.DataFrame(index=df.index)
    out["close_to_close"] = r.rolling(n).std()
    for k in ("parkinson", "garman_klass", "rogers_satchell"):
        out[k] = d[k].rolling(n).mean().clip(lower=0) ** 0.5
    on = np.log(df["open"] / df["close"].shift())                       # "overnight" jump (tiny in 24/7 markets)
    oc = np.log(df["close"] / df["open"])
    kk = 0.34 / (1.34 + (n + 1) / (n - 1))
    out["yang_zhang"] = (on.rolling(n).var() + kk * oc.rolling(n).var()
                         + (1 - kk) * d["rogers_satchell"].rolling(n).mean()).clip(lower=0) ** 0.5
    return out * math.sqrt(ANN) * 100


# ---------------------------------------------------------------- GARCH(1,1), fitted by maximum likelihood
def garch_filter(r, w, a, b):
    h = np.empty(len(r) + 1)
    h[0] = r.var()
    for t in range(len(r)):
        h[t + 1] = w + a * r[t] ** 2 + b * h[t]
    return h                                           # h[t] = variance for day t given info up to t-1; h[-1] = next day


def garch_fit(r, x0=None):
    """Gaussian quasi-MLE on demeaned % returns. Returns (omega, alpha, beta)."""
    r = np.asarray(r, float)
    v = r.var()

    def nll(p):
        w, a, b = p
        if w <= 0 or a < 0 or b < 0 or a + b >= 0.9995:
            return 1e12
        h = garch_filter(r, w, a, b)[:-1]
        return 0.5 * np.sum(np.log(h) + r ** 2 / h)

    starts = [x0] if x0 is not None else []
    starts += [(v * 0.05, 0.08, 0.90), (v * 0.15, 0.15, 0.75)]
    best = None
    for s in starts:
        res = optimize.minimize(nll, s, method="Nelder-Mead", options=dict(maxiter=4000, xatol=1e-7, fatol=1e-7))
        if best is None or res.fun < best.fun:
            best = res
    return tuple(best.x)


def garch_t_fit(r):
    """GARCH(1,1) with Student-t errors (heavy tails), maximum likelihood. Returns (omega, alpha, beta, nu)."""
    r = np.asarray(r, float)
    v = r.var()
    from scipy.special import gammaln

    def nll(p):
        w, a, b, nu = p
        if w <= 0 or a < 0 or b < 0 or a + b >= 0.9995 or not 2.05 < nu < 100:
            return 1e12
        h = garch_filter(r, w, a, b)[:-1]
        return -np.sum(gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(np.pi * (nu - 2) * h)
                       - (nu + 1) / 2 * np.log1p(r ** 2 / ((nu - 2) * h)))

    best = None
    for s in [(v * 0.05, 0.08, 0.90, 4.0), (v * 0.15, 0.15, 0.75, 6.0), (v * 0.02, 0.05, 0.93, 3.0)]:
        res = optimize.minimize(nll, s, method="Nelder-Mead", options=dict(maxiter=6000, xatol=1e-7, fatol=1e-7))
        if best is None or res.fun < best.fun:
            best = res
    return tuple(best.x)


def walk_forward_forecasts(df, first=730, refit=30):
    """1-day-ahead variance forecasts made with past data only: GARCH(1,1), EWMA(0.94), rolling 30-day."""
    r = (np.log(df["close"]).diff().dropna() * 100)
    vals, idx = r.values, r.index
    g = np.full(len(vals), np.nan)
    params, p = [], None
    for s in range(first, len(vals), refit):
        hist = vals[:s]
        mu = hist.mean()
        p = garch_fit(hist - mu, p)
        params.append((idx[s], *p))
        e = min(s + refit, len(vals))
        h = garch_filter(vals[:e] - mu, *p)
        g[s:e] = h[s:e]
    ew = np.full(len(vals), np.nan)
    v = vals[:30].var()
    for t in range(len(vals)):
        ew[t] = v
        v = 0.94 * v + 0.06 * vals[t] ** 2
    roll = pd.Series(vals).rolling(30).var().shift(1).values
    out = pd.DataFrame(dict(r=vals, garch=g, ewma=ew, rolling30=roll), index=idx)
    gk = daily_variance_estimators(df)["garman_klass"].reindex(idx) * 1e4
    out["proxy_r2"], out["proxy_gk"] = out["r"] ** 2, gk.clip(lower=1e-6)
    return out.iloc[first:], pd.DataFrame(params, columns=["refit_date", "omega", "alpha", "beta"])


def forecast_scores(fc):
    """Losses robust to noisy volatility proxies (Patton 2011): QLIKE = log h + proxy/h, and MSE."""
    rows, models = [], ["garch", "ewma", "rolling30"]
    losses = {}
    for proxy in ("proxy_r2", "proxy_gk"):
        for m in models:
            q = np.log(fc[m]) + fc[proxy] / fc[m]
            mse = (fc[proxy] - fc[m]) ** 2
            losses[(proxy, m)] = q
            rows.append(dict(proxy=proxy.replace("proxy_", ""), model=m, qlike=q.mean(), mse=mse.mean()))
    dm = {}
    for proxy in ("proxy_r2", "proxy_gk"):
        for m in ("ewma", "rolling30"):
            d = (losses[(proxy, "garch")] - losses[(proxy, m)]).values
            dm[f"garch_vs_{m}_{proxy.replace('proxy_', '')}"] = round(nw_tstat(d), 2)
    return pd.DataFrame(rows), dm


# ---------------------------------------------------------------- charts
def mark_events(ax, ymax_frac=0.97, labels=True):
    lo, hi = ax.get_xlim()
    for d, name in EVENTS:
        x = mdates.date2num(pd.Timestamp(d))
        if lo <= x <= hi:
            ax.axvline(x, color=AXIS, lw=0.9, ls=(0, (3, 3)), zorder=1)
            if labels:
                ax.text(x, ymax_frac, " " + name, transform=ax.get_xaxis_transform(), fontsize=8, color=INK2,
                        rotation=90, va="top", ha="left")


def finish(fig, path, note=None):
    if note:
        fig.text(0.01, 0.005, note, fontsize=8, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03 if note else 0, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def date_axis(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


# ---------------------------------------------------------------- part 1: volatility
def part_volatility(data, dvol, out, S):
    btc = data["BTC"]
    rv = rolling_vols(btc)

    # 1a. estimators side by side (3 series max per chart)
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for k, col, lab in (("close_to_close", S1, "Close-to-close"), ("parkinson", S2, "Parkinson (high-low)"),
                        ("yang_zhang", S3, "Yang-Zhang")):
        ax.plot(rv.index, rv[k], color=col, lw=1.4, label=lab)
    ax.set_title("BTC 30-day realized volatility: three estimators")
    ax.set_ylabel("Annualized volatility (%)")
    date_axis(ax)
    ax.legend(loc="upper right", ncol=3)
    finish(fig, os.path.join(out, "01_btc_vol_estimators.png"),
           "Source: Binance daily candles. Range-based estimators use the daily high and low, not just the close.")

    # 1b. which estimator forecasts next month best (non-overlapping 30-day blocks)
    r = np.log(btc["close"]).diff()
    fut = r[::-1].rolling(30).std()[::-1].shift(-1) * math.sqrt(ANN) * 100       # realized over t+1..t+30
    blocks = rv.join(fut.rename("future")).dropna().iloc[::30]
    est_rows = []
    for k in rv.columns:
        e = blocks[k] - blocks["future"]
        est_rows.append(dict(estimator=k, mean_level=round(rv[k].mean(), 1),
                             bias_vs_future=round(e.mean(), 2), rmse=round(math.sqrt((e ** 2).mean()), 2),
                             corr_with_future=round(blocks[k].corr(blocks["future"]), 3),
                             noise_ratio=round((rv[k].diff().std() / rv["close_to_close"].diff().std()), 2)))
    est = pd.DataFrame(est_rows)
    S["estimators"] = est.to_dict("records")
    S["estimator_blocks"] = len(blocks)

    # 1c. clustering: autocorrelation of returns vs absolute returns
    rr = r.dropna()
    lags = np.arange(1, 61)
    ac_r = [rr.autocorr(L) for L in lags]
    ac_a = [rr.abs().autocorr(L) for L in lags]
    n = len(rr)
    band = 1.96 / math.sqrt(n)
    q20 = n * (n + 2) * sum((rr ** 2).autocorr(L) ** 2 / (n - L) for L in range(1, 21))
    S["clustering"] = dict(ljung_box_q20_squared_returns=round(q20, 1), p_value=float(stats.chi2.sf(q20, 20)),
                           acf_abs_lag1=round(ac_a[0], 3), acf_abs_lag30=round(ac_a[29], 3),
                           acf_ret_lag1=round(ac_r[0], 3), n_days=n)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.axhspan(-band, band, color=GRID, alpha=0.8, lw=0)
    ax.plot(lags, ac_r, color=NEUTRAL, lw=1.4, marker="o", ms=3, label="Returns")
    ax.plot(lags, ac_a, color=S1, lw=1.6, marker="o", ms=3, label="Absolute returns (size of the move)")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_title("BTC: direction is unpredictable, the size of moves is not")
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Autocorrelation")
    ax.legend(loc="upper right")
    finish(fig, os.path.join(out, "02_btc_volatility_clustering.png"),
           "Shaded band = 95% range for pure noise. Large moves are followed by large moves for weeks.")

    # 1d. GARCH walk-forward vs simple models, for BTC and ETH
    S["garch"] = {}
    for coin in ("BTC", "ETH"):
        if coin not in data:
            continue
        fc, params = walk_forward_forecasts(data[coin])
        sc, dm = forecast_scores(fc)
        last = params.iloc[-1]
        pers = last["alpha"] + last["beta"]
        S["garch"][coin] = dict(
            forecast_days=len(fc), refits=len(params),
            last_alpha=round(last["alpha"], 3), last_beta=round(last["beta"], 3), persistence=round(pers, 4),
            shock_half_life_days=round(math.log(0.5) / math.log(pers), 1) if 0 < pers < 1 else None,
            scores=sc.round(4).to_dict("records"), dm_tstats=dm)
        if coin == "BTC":
            fig, ax = plt.subplots(figsize=(10, 4.6))
            ann = lambda v: np.sqrt(v * ANN)                            # daily %^2 -> annualized %
            ax.plot(fc.index, ann(fc["proxy_gk"].rolling(7).mean()), color=NEUTRAL, lw=1.0,
                    label="Realized (7-day avg of daily range estimate)")
            ax.plot(fc.index, ann(fc["garch"]), color=S1, lw=1.5, label="GARCH(1,1) forecast, made the day before")
            ax.set_title("BTC: next-day volatility forecast vs what happened")
            ax.set_ylabel("Annualized volatility (%)")
            date_axis(ax)
            ax.legend(loc="upper right")
            finish(fig, os.path.join(out, "03_btc_garch_forecast.png"),
                   f"Walk-forward, refitted every 30 days on past data only ({len(params)} refits). The forecast is a mean; "
                   f"the grey proxy is typical-day, so it sits lower outside spikes.")

    # 1e. persistence across coins (full-sample fit, informative only)
    pers_rows = []
    for c, df in data.items():
        rr_c = (np.log(df["close"]).diff().dropna() * 100)
        if len(rr_c) < 900:
            continue
        w, a, b, nu = garch_t_fit(rr_c - rr_c.mean())
        pers = a + b
        boundary = pers >= 0.999
        pers_rows.append(dict(coin=c, days=len(rr_c), ann_vol_full=round(rr_c.std() * math.sqrt(ANN), 1),
                              ann_vol_last_365=round(rr_c.iloc[-365:].std() * math.sqrt(ANN), 1),
                              alpha=round(a, 3), beta=round(b, 3), persistence=round(pers, 4),
                              half_life_days=("n/a (near 1)" if boundary else round(math.log(0.5) / math.log(pers), 1)),
                              t_dof=round(nu, 1), excess_kurtosis=round(stats.kurtosis(rr_c), 1)))
    S["coin_vol_table"] = sorted(pers_rows, key=lambda d: -d["ann_vol_last_365"])

    # 1f. asymmetry: is volatility higher after down days or after up days of the same size?
    d = pd.DataFrame(dict(r=r))
    d["next5"] = r[::-1].rolling(5).std()[::-1].shift(-1) * math.sqrt(ANN) * 100
    d["prev30"] = r.rolling(30).std() * math.sqrt(ANN) * 100
    d["z"] = d["r"] / r.rolling(30).std().shift(1)
    d = d.dropna()
    big_dn, big_up = d[d["z"] < -1.5], d[d["z"] > 1.5]
    ratio = lambda g: (g["next5"] / g["prev30"]).mean()
    S["asymmetry"] = dict(n_big_down=len(big_dn), n_big_up=len(big_up),
                          vol_ratio_after_big_down=round(ratio(big_dn), 3),
                          vol_ratio_after_big_up=round(ratio(big_up), 3),
                          diff_t=round(stats.ttest_ind(big_dn["next5"] / big_dn["prev30"],
                                                       big_up["next5"] / big_up["prev30"], equal_var=False)[0], 2))

    # 1g. implied (DVOL) vs realized afterwards
    if dvol is not None and len(dvol) > 200:
        fut_rv = (r[::-1].rolling(30).std()[::-1].shift(-1) * math.sqrt(ANN) * 100).rename("rv_next30")
        j = pd.concat([dvol, fut_rv], axis=1).dropna()
        j["vrp"] = j["dvol"] - j["rv_next30"]
        by_year = j.groupby(j.index.year)["vrp"].agg(["mean", "count"]).round(1)
        S["implied_vs_realized"] = dict(
            days=len(j), mean_dvol=round(j["dvol"].mean(), 1), mean_realized_next30=round(j["rv_next30"].mean(), 1),
            mean_premium=round(j["vrp"].mean(), 2), premium_t_newey_west=round(nw_tstat(j["vrp"].values, 30), 2),
            share_days_implied_above=round((j["vrp"] > 0).mean() * 100, 1),
            worst_day_premium=round(j["vrp"].min(), 1),
            by_year={int(k): dict(mean=float(v["mean"]), days=int(v["count"])) for k, v in by_year.iterrows()})
        fig, ax = plt.subplots(figsize=(10, 4.6))
        ax.plot(j.index, j["dvol"], color=S1, lw=1.5, label="Implied (Deribit DVOL), known on the day")
        ax.plot(j.index, j["rv_next30"], color=S2, lw=1.3, label="Realized over the next 30 days")
        ax.set_title("BTC: what options priced vs what the market then delivered")
        ax.set_ylabel("Annualized volatility (%)")
        date_axis(ax)
        ax.legend(loc="upper right")
        finish(fig, os.path.join(out, "04_btc_implied_vs_realized.png"),
               "Implied above realized = options were 'expensive'. The gap is the volatility risk premium.")


# ---------------------------------------------------------------- part 3: correlation and structure
def returns_panel(data, start, min_cov=0.98):
    px = pd.DataFrame({c: df["close"] for c, df in data.items()})
    px = px.loc[px.index >= pd.Timestamp(start)]
    keep = [c for c in px.columns if px[c].notna().mean() >= min_cov]
    px = px[keep].ffill().dropna()
    return np.log(px).diff().dropna()


def exceedance_corr(x, y, qs):
    """Longin-Solnik exceedance correlation on standardized series: both below q (q<0.5) or both above q (q>0.5)."""
    out = []
    for q in qs:
        if q < 0.5:
            m = (x < np.quantile(x, q)) & (y < np.quantile(y, q))
        else:
            m = (x > np.quantile(x, q)) & (y > np.quantile(y, q))
        out.append(np.corrcoef(x[m], y[m])[0, 1] if m.sum() >= 15 else np.nan)
    return np.array(out)


def part_structure(data, xs_start, out, S, seed=1):
    R = returns_panel(data, xs_start)
    coins = list(R.columns)
    S["panel"] = dict(coins=coins, n_coins=len(coins), start=str(R.index[0].date()), end=str(R.index[-1].date()),
                      days=len(R))
    if "BTC" not in coins or len(coins) < 8:
        S["panel"]["error"] = "not enough coins with full history"
        return

    # 3a. PCA: how much of all coins' risk is one common factor?
    Z = (R - R.mean()) / R.std()
    ev, evec = np.linalg.eigh(np.corrcoef(Z.values.T))
    ev, evec = ev[::-1], evec[:, ::-1]
    pc1 = evec[:, 0] * np.sign(evec[:, 0].sum())
    S["pca_full"] = dict(pc1_share=round(ev[0] / ev.sum() * 100, 1), pc2_share=round(ev[1] / ev.sum() * 100, 1),
                         pc3_share=round(ev[2] / ev.sum() * 100, 1),
                         pc1_loadings_min=round(pc1.min(), 3), pc1_loadings_max=round(pc1.max(), 3),
                         equal_weight_loading=round(1 / math.sqrt(len(coins)), 3))
    win = 90
    share, eff_bets, avg_corr, dates = [], [], [], []
    w = np.full(len(coins), 1 / len(coins))
    for e in range(win, len(R) + 1, 5):
        blk = R.iloc[e - win:e].values
        C = np.corrcoef(blk.T)
        lam = np.linalg.eigvalsh(C)
        share.append(lam[-1] / lam.sum() * 100)
        cov = np.cov(blk.T)
        sd = np.sqrt(np.diag(cov))
        dr = (w @ sd) / math.sqrt(w @ cov @ w)                          # diversification ratio (Choueifaty)
        eff_bets.append(dr ** 2)
        avg_corr.append(C[np.triu_indices(len(coins), 1)].mean())
        dates.append(R.index[e - 1])
    roll = pd.DataFrame(dict(pc1_share=share, effective_bets=eff_bets, avg_corr=avg_corr), index=dates)
    ev_rows = {}
    for d0, name in EVENTS:
        t = pd.Timestamp(d0)
        if roll.index[0] <= t <= roll.index[-1]:
            after = roll.loc[t:t + pd.Timedelta(days=30)]
            before = roll.loc[t - pd.Timedelta(days=60):t - pd.Timedelta(days=1)]
            btc_ret = R["BTC"].loc[t:t + pd.Timedelta(days=2)].sum() * 100 if t in R.index else None
            if len(after) and len(before):
                ev_rows[name] = dict(date=d0, btc_move_3d_pct=None if btc_ret is None else round(btc_ret, 1),
                                     effective_bets_before=round(before["effective_bets"].median(), 2),
                                     effective_bets_after=round(after["effective_bets"].min(), 2),
                                     pc1_share_before=round(before["pc1_share"].median(), 1),
                                     pc1_share_after=round(after["pc1_share"].max(), 1))
    S["rolling_structure"] = dict(window_days=win, n_coins=len(coins),
                                  effective_bets_median=round(roll["effective_bets"].median(), 2),
                                  effective_bets_min=round(roll["effective_bets"].min(), 2),
                                  effective_bets_max=round(roll["effective_bets"].max(), 2),
                                  pc1_share_median=round(roll["pc1_share"].median(), 1),
                                  avg_corr_median=round(roll["avg_corr"].median(), 3), events=ev_rows)

    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(roll.index, roll["effective_bets"], color=S1, lw=1.6)
    ax.axhline(roll["effective_bets"].median(), color=INK2, lw=0.9, ls=(0, (1, 2)))
    ax.text(1.0, roll["effective_bets"].median(), f" median {roll['effective_bets'].median():.1f}",
            va="center", ha="left", fontsize=8, color=INK2, transform=ax.get_yaxis_transform())
    ax.set_ylim(1, max(roll["effective_bets"].max() * 1.15, 2))
    ax.set_title(f"A basket of {len(coins)} coins behaves like about {roll['effective_bets'].median():.1f} independent bets")
    ax.set_ylabel("Effective number of bets")
    date_axis(ax)
    mark_events(ax)
    finish(fig, os.path.join(out, "05_effective_bets.png"),
           f"Rolling {win}-day window. Effective bets = diversification ratio squared. Dotted lines = stress events.")

    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(roll.index, roll["pc1_share"], color=S1, lw=1.6)
    ax.set_ylim(0, 100)
    ax.set_title("Share of all coins' risk explained by one common factor")
    ax.set_ylabel("First principal component (% of variance)")
    date_axis(ax)
    mark_events(ax)
    finish(fig, os.path.join(out, "06_pca_market_factor.png"), f"Rolling {win}-day PCA on {len(coins)} coins.")

    # 3b. beta and R^2 to BTC: market risk vs coin-specific risk
    b_rows, x = [], R["BTC"].values
    for c in coins:
        if c == "BTC":
            continue
        for label, sl in (("full", slice(None)), ("last_365", slice(-365, None))):
            y = R[c].values[sl]
            xx = x[sl]
            beta = np.cov(xx, y)[0, 1] / xx.var(ddof=1)
            r2 = np.corrcoef(xx, y)[0, 1] ** 2
            b_rows.append(dict(coin=c, period=label, beta=round(beta, 2), r2=round(r2, 3)))
    B = pd.DataFrame(b_rows)
    P = B.pivot(index="coin", columns="period", values=["beta", "r2"]).round(3)
    P.columns = [f"{v}_{p}" for v, p in P.columns]
    S["beta_table"] = P.reset_index().sort_values("r2_full", ascending=False).to_dict("records")
    full = B[B.period == "full"].sort_values("r2")
    S["beta_summary"] = dict(median_beta=round(full["beta"].median(), 2), median_r2=round(full["r2"].median(), 3),
                             min_r2_coin=full.iloc[0]["coin"], min_r2=full.iloc[0]["r2"],
                             max_r2_coin=full.iloc[-1]["coin"], max_r2=full.iloc[-1]["r2"])
    fig, ax = plt.subplots(figsize=(10, max(4.2, 0.26 * len(full) + 1.2)))
    yy = np.arange(len(full))
    ax.barh(yy, full["r2"] * 100, color=S1, height=0.72, edgecolor=SURF, lw=1, label="Explained by BTC")
    ax.barh(yy, (1 - full["r2"]) * 100, left=full["r2"] * 100, color=GRID, height=0.72, edgecolor=SURF, lw=1,
            label="Coin-specific")
    for i, (r2_, bt) in enumerate(zip(full["r2"], full["beta"])):
        if r2_ >= 0.12:
            ax.text(r2_ * 100 - 1, i, f"{r2_*100:.0f}%", va="center", ha="right", fontsize=7.5, color="white")
        else:
            ax.text(r2_ * 100 + 1, i, f"{r2_*100:.0f}%", va="center", ha="left", fontsize=7.5, color=INK2)
        ax.text(101, i, f"beta {bt:.2f}", va="center", ha="left", fontsize=7.5, color=INK2)
    ax.set_yticks(yy)
    ax.set_yticklabels(full["coin"])
    ax.set_xlim(0, 112)
    ax.set_xlabel("Share of daily variance (%)")
    ax.grid(axis="y", visible=False)
    ax.set_title("How much of each coin's daily risk is just BTC")
    ax.legend(loc="lower right", ncol=2, bbox_to_anchor=(1, 1.0))
    finish(fig, os.path.join(out, "07_beta_r2_to_btc.png"),
           f"Daily log returns {S['panel']['start']} to {S['panel']['end']}. Beta = move per 1% move in BTC.")

    # 3c. exceedance correlation vs what a normal distribution would give
    qs = np.array([0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80,
                   0.85, 0.90, 0.95])
    rng = np.random.default_rng(seed)
    emp, nor = [], []
    xs = (R["BTC"] - R["BTC"].mean()) / R["BTC"].std()
    for c in coins:
        if c == "BTC":
            continue
        ys = (R[c] - R[c].mean()) / R[c].std()
        emp.append(exceedance_corr(xs.values, ys.values, qs))
        rho = np.corrcoef(xs, ys)[0, 1]
        sim = rng.multivariate_normal([0, 0], [[1, rho], [rho, 1]], 200_000)
        nor.append(exceedance_corr(sim[:, 0], sim[:, 1], qs))
    fz = lambda a: np.tanh(np.nanmean(np.arctanh(np.clip(np.array(a), -0.999, 0.999)), axis=0))
    E, N = fz(emp), fz(nor)
    # moving-block bootstrap over days (10-day blocks keep volatility clusters together)
    alts = [c for c in coins if c != "BTC"]
    Zs = ((R - R.mean()) / R.std()).values
    ib, ia = coins.index("BTC"), [coins.index(c) for c in alts]
    nT, blk, diffs = len(R), 10, []
    for _ in range(300):
        starts = rng.integers(0, nT - blk, nT // blk + 1)
        idx = (starts[:, None] + np.arange(blk)).ravel()[:nT]
        Zb = Zs[idx]
        ec = [exceedance_corr(Zb[:, ib], Zb[:, j], np.array([0.10, 0.90])) for j in ia]
        e2 = fz(ec)
        diffs.append(e2[0] - e2[1])
    diffs = np.array(diffs)
    lo, hi = qs < 0.5, qs > 0.5
    S["exceedance"] = dict(quantiles=qs.tolist(), empirical=np.round(E, 3).tolist(), normal=np.round(N, 3).tolist(),
                           at_10pct_down=dict(empirical=round(float(E[1]), 3), normal=round(float(N[1]), 3)),
                           at_10pct_up=dict(empirical=round(float(E[-2]), 3), normal=round(float(N[-2]), 3)),
                           down_minus_up_10pct=round(float(E[1] - E[-2]), 3),
                           bootstrap_95ci=[round(float(np.nanpercentile(diffs, 2.5)), 3),
                                           round(float(np.nanpercentile(diffs, 97.5)), 3)],
                           bootstrap_share_above_0=round(float((diffs > 0).mean()), 3))
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for msk in (lo, hi):
        ax.plot(qs[msk] * 100, E[msk], color=S1, lw=1.8, marker="o", ms=4,
                label="Actual crypto returns" if msk is lo else None)
        ax.plot(qs[msk] * 100, N[msk], color=NEUTRAL, lw=1.6, ls=(0, (4, 2)), marker="o", ms=3,
                label="If returns were normal (same overall correlation)" if msk is lo else None)
    ax.axvline(50, color=AXIS, lw=0.8)
    ax.set_xlabel("Threshold percentile of daily return   (left of 50: both falling together  |  right: both rising together)")
    ax.set_ylabel("Correlation with BTC beyond threshold")
    ax.set_title("Diversification fails exactly when it is needed: correlation in the tails")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    ax.set_title("Diversification fails exactly when it is needed: correlation in the tails", pad=26)
    finish(fig, os.path.join(out, "08_exceedance_correlation.png"),
           f"Longin-Solnik exceedance correlation, average over {len(coins)-1} coins vs BTC (Fisher-z mean).")

    # 3d. clustered correlation heatmap, last 365 days
    last = R.iloc[-365:]
    C = last.corr()
    link = hierarchy.linkage(squareform(1 - C.values, checks=False), "average")
    order = hierarchy.leaves_list(link)
    C = C.iloc[order, order]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", ["#f0efec", "#b7d3f6", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"])
    fig, ax = plt.subplots(figsize=(8.6, 7.6))
    im = ax.imshow(C.values, cmap=cmap, vmin=0, vmax=1)
    ax.set_xticks(range(len(C)))
    ax.set_xticklabels(C.columns, rotation=90, fontsize=8)
    ax.set_yticks(range(len(C)))
    ax.set_yticklabels(C.index, fontsize=8)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label("Correlation of daily returns", color=INK2)
    ax.set_title("Correlation map, last 365 days (similar coins grouped together)")
    finish(fig, os.path.join(out, "09_correlation_heatmap.png"))
    upper = C.values[np.triu_indices(len(C), 1)]
    S["heatmap_last365"] = dict(avg_pairwise=round(upper.mean(), 3), min_pairwise=round(upper.min(), 3),
                                max_pairwise=round(upper.max(), 3))


# ---------------------------------------------------------------- report
def md_table(rows, cols=None):
    if not rows:
        return "_none_\n"
    df = pd.DataFrame(rows)
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    df.columns = [c if isinstance(c, str) else " ".join(str(x) for x in c if x) for c in df.columns]
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "".join("| " + " | ".join("" if (isinstance(v, float) and math.isnan(v)) else str(v) for v in r) + " |\n"
                          for r in df.itertuples(index=False))


def write_report(S, out):
    L = [f"# Crypto Risk Lab - results\n\nGenerated {S['generated_utc']} | data: {S['source']}\n"]
    L.append("## Part 1 - Volatility\n\n### Estimators (BTC, 30-day window)\n")
    L.append(md_table(S["estimators"]))
    L.append(f"\n_bias/rmse/corr measured against realized close-to-close volatility of the NEXT 30 days, "
             f"{S['estimator_blocks']} non-overlapping blocks. noise_ratio = day-to-day jitter vs close-to-close._\n")
    c = S["clustering"]
    L.append(f"\n### Volatility clustering (BTC, {c['n_days']} days)\n\n- autocorrelation of returns at lag 1: "
             f"{c['acf_ret_lag1']}\n- autocorrelation of absolute returns: lag 1 = {c['acf_abs_lag1']}, lag 30 = "
             f"{c['acf_abs_lag30']}\n- Ljung-Box Q(20) on squared returns = {c['ljung_box_q20_squared_returns']} "
             f"(p = {c['p_value']:.2e})\n")
    for coin, g in S.get("garch", {}).items():
        L.append(f"\n### GARCH(1,1) walk-forward, {coin}\n\n{g['forecast_days']} out-of-sample days, {g['refits']} "
                 f"refits. Latest fit: alpha {g['last_alpha']}, beta {g['last_beta']}, persistence "
                 f"{g['persistence']}, half-life of a volatility shock {g['shock_half_life_days']} days.\n\n")
        L.append(md_table(g["scores"]))
        L.append(f"\nDiebold-Mariano t-stats (negative = GARCH better): {g['dm_tstats']}\n")
    L.append("\n### Volatility by coin (full-sample GARCH(1,1) with Student-t errors)\n\n")
    L.append(md_table(S["coin_vol_table"]))
    a = S["asymmetry"]
    L.append(f"\n### Asymmetry (BTC)\n\nNext-5-day vol / previous-30-day vol after big DOWN days "
             f"({a['n_big_down']}): {a['vol_ratio_after_big_down']}; after big UP days ({a['n_big_up']}): "
             f"{a['vol_ratio_after_big_up']}; Welch t = {a['diff_t']}\n")
    if "implied_vs_realized" in S:
        v = S["implied_vs_realized"]
        L.append(f"\n### Implied (DVOL) vs realized next 30 days (BTC, {v['days']} days)\n\n- mean DVOL "
                 f"{v['mean_dvol']}, mean realized {v['mean_realized_next30']}, mean premium {v['mean_premium']} "
                 f"vol points (Newey-West t {v['premium_t_newey_west']})\n- implied above realized on "
                 f"{v['share_days_implied_above']}% of days; worst {v['worst_day_premium']}\n- by year: "
                 f"{v['by_year']}\n")
    else:
        L.append("\n_Deribit DVOL not available in this run._\n")
    p = S["panel"]
    L.append(f"\n## Part 3 - Correlation and market structure\n\nPanel: {p['n_coins']} coins with full history, "
             f"{p['start']} to {p['end']} ({p['days']} days): {', '.join(p['coins'])}\n")
    if "pca_full" in S:
        q = S["pca_full"]
        L.append(f"\n### PCA (full sample)\n\nPC1 {q['pc1_share']}%, PC2 {q['pc2_share']}%, PC3 {q['pc3_share']}% of "
                 f"variance. PC1 loadings range {q['pc1_loadings_min']} to {q['pc1_loadings_max']} (equal weight "
                 f"would be {q['equal_weight_loading']}).\n")
        r = S["rolling_structure"]
        L.append(f"\n### Rolling {r['window_days']}-day structure\n\n- effective number of bets (equal weight, "
                 f"{r['n_coins']} coins): median {r['effective_bets_median']}, min {r['effective_bets_min']}, max "
                 f"{r['effective_bets_max']}\n- PC1 share median {r['pc1_share_median']}%, average pairwise "
                 f"correlation median {r['avg_corr_median']}\n\nAround stress events:\n\n")
        L.append(md_table([dict(event=k, **v) for k, v in r["events"].items()]))
        bs = S["beta_summary"]
        L.append(f"\n### Beta and R^2 to BTC\n\nMedian beta {bs['median_beta']}, median R^2 {bs['median_r2']} "
                 f"(lowest {bs['min_r2_coin']} {bs['min_r2']}, highest {bs['max_r2_coin']} {bs['max_r2']}).\n\n")
        L.append(md_table(S["beta_table"]))
        e = S["exceedance"]
        L.append(f"\n### Exceedance correlation with BTC\n\nAt the 10% tail: DOWN {e['at_10pct_down']}, UP "
                 f"{e['at_10pct_up']}; down minus up = {e['down_minus_up_10pct']} (block-bootstrap 95% CI {e['bootstrap_95ci']}, "
                 f"share of resamples above 0: {e['bootstrap_share_above_0']})\n\n")
        L.append(md_table([dict(q=q_, empirical=a_, normal=b_) for q_, a_, b_ in
                           zip(e["quantiles"], e["empirical"], e["normal"])]))
        h = S["heatmap_last365"]
        L.append(f"\n### Last 365 days\n\nAverage pairwise correlation {h['avg_pairwise']} (min {h['min_pairwise']}, "
                 f"max {h['max_pairwise']})\n")
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as f:
        f.write("".join(L))
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(S, f, indent=1, default=str)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true", help="fake data, checks the code runs")
    ap.add_argument("--start", default="2019-01-01", help="history start for the volatility part")
    ap.add_argument("--xs-start", default="2021-01-01", help="start of the cross-section (correlation) panel")
    ap.add_argument("--cache", default="risk_cache")
    ap.add_argument("--out", default="results")
    ap.add_argument("--no-deribit", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    S = dict(generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
             source="SYNTHETIC (test only)" if a.synthetic else "Binance daily candles; Deribit DVOL")

    if a.synthetic:
        data, dvol = synthetic_market()
    else:
        data = {}
        for c in UNIVERSE:
            try:
                data[c] = fetch_daily(c, a.start, a.cache)
                print(f"fetched {c}: {len(data[c])} days from {data[c].index[0]:%Y-%m-%d}", flush=True)
            except Exception as e:
                print(f"skip {c}: {e}", flush=True)
        dvol = None
        if not a.no_deribit:
            try:
                dvol = fetch_dvol("BTC", "2021-03-24", a.cache)
                print(f"fetched BTC DVOL: {len(dvol)} days", flush=True)
            except Exception as e:
                print(f"DVOL not available ({e}); that chart is skipped", flush=True)
    print("NOTE: only coins still listed today are included (survivorship bias).", flush=True)

    print("Part 1: volatility ...", flush=True)
    part_volatility(data, dvol, a.out, S)
    print("Part 3: correlation and market structure ...", flush=True)
    part_structure(data, a.xs_start, a.out, S)
    write_report(S, a.out)
    print(f"\nDone. Open the folder '{a.out}': charts (PNG) + summary.md", flush=True)


if __name__ == "__main__":
    main()
