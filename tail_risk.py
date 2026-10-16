#!/usr/bin/env python3
"""
Crypto Risk Lab - Part 2: tail risk, Value at Risk and Expected Shortfall, with formal backtests.

For BTC, ETH and an equal-weight basket of coins, six VaR/ES models forecast tomorrow's risk using only
past data. Each forecast is then checked against what actually happened:
  * Kupiec test         - is the NUMBER of VaR breaches right?
  * Christoffersen test - do breaches come in CLUSTERS (several bad days in a row)?
  * Basel traffic light - how a bank regulator would grade the model (99% VaR, 250-day windows)
  * ES check            - on breach days, was the loss as large as the model's Expected Shortfall said?

Usage (same folder as crypto_risk_lab.py, uses the same data cache):
  python tail_risk.py
  python tail_risk.py --synthetic      # fake data, only checks that the code runs
Output: results/10_..., 11_..., 12_..., 13_... charts and results/tail_summary.md / tail_summary.json
"""
import argparse, json, math, os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

import crypto_risk_lab as lab
from crypto_risk_lab import plt, mdates, SURF, INK, INK2, MUTED, GRID, AXIS, S1, S2, S3, NEUTRAL, finish, date_axis

LEVELS = (0.99, 0.975)
WINDOW = 500                      # estimation window (days) for every model
REFIT = 20                        # refit frequency (days) for the Student-t and EVT tail parameters
LAMBDA = 0.94                     # EWMA decay (RiskMetrics)
MODELS = ["normal", "historical", "ewma_normal", "ewma_t", "filtered_hs", "evt"]
LABELS = {"normal": "Normal (rolling)", "historical": "Historical simulation", "ewma_normal": "EWMA + normal",
          "ewma_t": "EWMA + Student-t", "filtered_hs": "Filtered historical", "evt": "EWMA + EVT (GPD tail)"}


# ---------------------------------------------------------------- data
def build_assets(data, xs_start):
    """BTC, ETH and an equal-weight, daily-rebalanced basket. Returns daily log returns in %."""
    out = {}
    for c in ("BTC", "ETH"):
        if c in data:
            out[c] = np.log(data[c]["close"]).diff().dropna() * 100
    R = lab.returns_panel(data, xs_start)                     # log returns, coins with full history
    simple = np.expm1(R)
    out[f"Basket ({R.shape[1]} coins)"] = np.log1p(simple.mean(axis=1)) * 100
    return out


# ---------------------------------------------------------------- models
def ewma_sigma(r):
    """sigma[t] = EWMA volatility for day t using returns up to t-1 only."""
    s = np.empty(len(r))
    v = np.var(r[:30])
    for t in range(len(r)):
        s[t] = math.sqrt(v)
        v = LAMBDA * v + (1 - LAMBDA) * r[t] ** 2
    return s


def std_t_var_es(nu, q):
    """VaR and ES (as positive numbers) of a Student-t scaled to unit variance, at confidence q."""
    k = math.sqrt((nu - 2) / nu)
    x = stats.t.ppf(1 - q, nu)                                  # left-tail quantile (negative)
    es = stats.t.pdf(x, nu) / (1 - q) * (nu + x ** 2) / (nu - 1)
    return -x * k, es * k


def gpd_var_es(losses, q, u_pct=0.90):
    """Peaks-over-threshold: fit a Generalized Pareto to losses above the 90th percentile (McNeil-Frey 2000)."""
    u = np.quantile(losses, u_pct)
    exc = losses[losses > u] - u
    xi, _, beta = stats.genpareto.fit(exc, floc=0)
    xi = min(xi, 0.9)
    n, nu = len(losses), len(exc)
    tail = (1 - q) * n / nu
    var = u + (beta / xi) * (tail ** (-xi) - 1) if abs(xi) > 1e-6 else u - beta * math.log(tail)
    es = var / (1 - xi) + (beta - xi * u) / (1 - xi)
    return var, es, xi


def forecast(r, q):
    """One-day-ahead VaR and ES (positive % losses) for every model, made with data up to the day before."""
    r = np.asarray(r, float)
    n = len(r)
    sig = ewma_sigma(r)
    z = r / sig
    zq = stats.norm.ppf(q)
    out = {m: np.full((n, 2), np.nan) for m in MODELS}
    nu, gpd, xi_hist = None, None, []
    for t in range(WINDOW, n):
        w, zw, s = r[t - WINDOW:t], z[t - WINDOW:t], sig[t]
        mu, sd = w.mean(), w.std(ddof=1)
        out["normal"][t] = (-mu + sd * zq, -mu + sd * stats.norm.pdf(zq) / (1 - q))
        hv = -np.quantile(w, 1 - q)
        out["historical"][t] = (hv, -w[w <= -hv].mean())
        out["ewma_normal"][t] = (s * zq, s * stats.norm.pdf(zq) / (1 - q))
        zs = zw.std(ddof=1)
        fv = -np.quantile(zw, 1 - q)
        out["filtered_hs"][t] = (fv * s, -zw[zw <= -fv].mean() * s)
        if nu is None or (t - WINDOW) % REFIT == 0:
            nu = float(np.clip(stats.t.fit(zw / zs, floc=0)[0], 2.2, 50))
            gpd = gpd_var_es(-zw, q)
            xi_hist.append(gpd[2])
        tv, te = std_t_var_es(nu, q)
        out["ewma_t"][t] = (tv * zs * s, te * zs * s)
        out["evt"][t] = (gpd[0] * s, gpd[1] * s)
    return out, sig, float(np.median(xi_hist)) if xi_hist else float("nan")


# ---------------------------------------------------------------- backtests
def kupiec(x, T, p):
    """Proportion-of-failures likelihood ratio test (Kupiec 1995). p-value: chi2 with 1 dof."""
    if T == 0:
        return float("nan")
    ph = x / T
    ll0 = (T - x) * math.log(1 - p) + x * math.log(p)
    ll1 = ((T - x) * math.log(1 - ph) if x < T else 0) + (x * math.log(ph) if x > 0 else 0)
    return float(stats.chi2.sf(-2 * (ll0 - ll1), 1))


def christoffersen(hits):
    """Independence test (Christoffersen 1998): does a breach today make a breach tomorrow more likely?"""
    h = np.asarray(hits, int)
    a, b = h[:-1], h[1:]
    n00, n01 = int(((a == 0) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())
    n10, n11 = int(((a == 1) & (b == 0)).sum()), int(((a == 1) & (b == 1)).sum())
    p01 = n01 / max(n00 + n01, 1)
    p11 = n11 / max(n10 + n11, 1)
    p = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)

    def ll(k, pr):
        return k * math.log(pr) if k > 0 and pr > 0 else 0.0
    l0 = ll(n00 + n10, 1 - p) + ll(n01 + n11, p)
    l1 = ll(n00, 1 - p01) + ll(n01, p01) + ll(n10, 1 - p11) + ll(n11, p11)
    return float(stats.chi2.sf(max(-2 * (l0 - l1), 0), 1)), n11


def traffic_light(hits99):
    """Basel: breaches of 99% VaR per 250 days -> green 0-4, yellow 5-9, red 10+. Share of rolling windows."""
    c = pd.Series(hits99).rolling(250).sum().dropna()
    if c.empty:
        return dict(green=None, yellow=None, red=None)
    return dict(green=round(float((c <= 4).mean()) * 100, 1), yellow=round(float(((c >= 5) & (c <= 9)).mean()) * 100, 1),
                red=round(float((c >= 10).mean()) * 100, 1), worst_window=int(c.max()))


def backtest(r, fc, sig, q, idx):
    rows, loss = [], -np.asarray(r, float)
    for m in MODELS:
        v, e = fc[m][:, 0], fc[m][:, 1]
        ok = np.isfinite(v)
        L, V, E, S = loss[ok], v[ok], e[ok], sig[ok]
        hits = (L > V).astype(int)
        T, x = len(hits), int(hits.sum())
        p_ind, n11 = christoffersen(hits)
        br = hits == 1
        es_ratio = float(L[br].mean() / E[br].mean()) if x else float("nan")
        es_t = float(stats.ttest_1samp((L[br] - E[br]) / S[br], 0).statistic) if x > 2 else float("nan")
        row = dict(model=m, days=T, breaches=x, expected=round(T * (1 - q), 1), ratio=round(x / (T * (1 - q)), 2),
                   kupiec_p=round(kupiec(x, T, 1 - q), 4), christoffersen_p=round(p_ind, 4), back_to_back=n11,
                   es_realized_over_predicted=round(es_ratio, 2), es_test_t=round(es_t, 2),
                   avg_var=round(float(V.mean()), 2))
        if q == 0.99:
            row.update({f"basel_{k}": v_ for k, v_ in traffic_light(hits).items()})
        rows.append(row)
    return rows


# ---------------------------------------------------------------- tail shape
def hill_alpha(r, frac=0.05):
    """Hill estimator of the LEFT-tail index on the largest 5% of losses. alpha < 4: kurtosis is infinite."""
    L = np.sort(-np.asarray(r))[::-1]
    L = L[L > 0]
    k = max(int(len(r) * frac), 10)
    return float(1 / np.mean(np.log(L[:k] / L[k])))


def tail_counts(r, sig):
    z = np.asarray(r) / sig
    z = z[np.isfinite(z)]
    T = len(z)
    rows = {}
    for k in (3, 4, 5):
        rows[f"down_beyond_{k}sd"] = dict(actual=int((z < -k).sum()), normal_expected=round(T * stats.norm.cdf(-k), 2))
    return rows, T


# ---------------------------------------------------------------- charts
def chart_qq(r, out):
    x = np.sort((r - r.mean()) / r.std())
    n = len(x)
    th = stats.norm.ppf((np.arange(1, n + 1) - 0.5) / n)
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    lim = max(abs(x).max(), abs(th).max()) * 1.05
    ax.plot([-lim, lim], [-lim, lim], color=AXIS, lw=1.0, ls=(0, (4, 3)), label="Normal distribution")
    ax.plot(th, x, "o", ms=3, color=S1, alpha=0.7, label="BTC daily returns")
    ax.set_xlim(-4.5, 4.5)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel("Normal quantile (standard deviations)")
    ax.set_ylabel("Actual return (standard deviations)")
    ax.set_title("BTC: the tails are far longer than a normal distribution")
    ax.legend(loc="upper left")
    finish(fig, os.path.join(out, "10_btc_qq_plot.png"),
           "Points off the dashed line at the ends = extreme days far more frequent and larger than 'normal'.")


def chart_var_path(idx, r, fc, out, q=0.99):
    L = -np.asarray(r)
    ok = np.isfinite(fc["normal"][:, 0])
    d = idx[ok]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(d, np.clip(L[ok], 0, None), width=1.0, color=NEUTRAL, label="Daily loss")
    ax.plot(d, fc["normal"][ok, 0], color=S2, lw=1.3, label="99% VaR, normal (rolling)")
    ax.plot(d, fc["evt"][ok, 0], color=S1, lw=1.5, label="99% VaR, EWMA + EVT")
    for m, col in (("normal", S2), ("evt", S1)):
        br = ok & (L > fc[m][:, 0])
        ax.plot(idx[br], L[br], "o", ms=4.5, mfc=SURF, mec=col, mew=1.5)
    ax.set_ylim(0, None)
    ax.set_ylabel("Loss (% per day)")
    ax.set_title("BTC: 99% VaR forecasts vs actual daily losses")
    date_axis(ax)
    ax.legend(loc="upper right", ncol=3)
    finish(fig, os.path.join(out, "11_btc_var_backtest.png"),
           "Circles = breaches (loss above the forecast, made the day before). A good 99% model breaches about 1 day in 100.")


def chart_ratios(results, out, q=0.99):
    assets = list(results)
    cols = [S1, S2, S3]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    y = np.arange(len(MODELS))
    h = 0.8 / len(assets)
    vmax = 1.0
    for i, a in enumerate(assets):
        rows = {rw["model"]: rw for rw in results[a][q]}
        vals = [rows[m]["ratio"] for m in MODELS]
        vmax = max(vmax, max(vals))
        pos = y - 0.4 + h * (i + 0.5)
        ax.barh(pos, vals, height=h * 0.92, color=cols[i], edgecolor=SURF, lw=1, label=a)
        for p_, v_ in zip(pos, vals):
            ax.text(v_ + 0.03, p_, f"{v_:.1f}x", va="center", fontsize=7.5, color=INK2)
    ax.axvline(1, color=INK, lw=1.0, ls=(0, (2, 2)))
    ax.text(1, len(MODELS) - 0.45, " correct = 1.0x", fontsize=8, color=INK2, va="bottom")
    ax.set_yticks(y)
    ax.set_yticklabels([LABELS[m] for m in MODELS])
    ax.invert_yaxis()
    ax.set_xlim(0, vmax * 1.15)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Breaches of 99% VaR, actual / expected")
    ax.set_title("Which risk models tell the truth? (99% VaR breaches vs expected)")
    ax.legend(loc="lower right")
    finish(fig, os.path.join(out, "12_var_breach_ratio_by_model.png"),
           "Above 1.0x = the model understates risk. Below 1.0x = too conservative.")


def chart_es(results, out, q=0.975):
    assets = list(results)
    cols = [S1, S2, S3]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    y = np.arange(len(MODELS))
    h = 0.8 / len(assets)
    vmax = 1.0
    for i, a in enumerate(assets):
        rows = {rw["model"]: rw for rw in results[a][q]}
        vals = [rows[m]["es_realized_over_predicted"] for m in MODELS]
        vmax = max(vmax, np.nanmax(vals))
        pos = y - 0.4 + h * (i + 0.5)
        ax.barh(pos, vals, height=h * 0.92, color=cols[i], edgecolor=SURF, lw=1, label=a)
        for p_, v_ in zip(pos, vals):
            ax.text(v_ + 0.02, p_, f"{v_:.2f}", va="center", fontsize=7.5, color=INK2)
    ax.axvline(1, color=INK, lw=1.0, ls=(0, (2, 2)))
    ax.set_yticks(y)
    ax.set_yticklabels([LABELS[m] for m in MODELS])
    ax.invert_yaxis()
    ax.set_xlim(0, vmax * 1.15)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("On breach days: actual average loss / predicted Expected Shortfall (97.5%)")
    ax.set_title("When the bad day comes, how bad is it compared with the forecast?")
    ax.legend(loc="lower right")
    finish(fig, os.path.join(out, "13_expected_shortfall_check.png"),
           "Above 1.0 = losses beyond VaR were larger than the model's Expected Shortfall predicted.")


# ---------------------------------------------------------------- report
def write_report(S, out):
    L = [f"# Crypto Risk Lab - Part 2: tail risk, VaR and Expected Shortfall\n\nGenerated {S['generated_utc']} | "
         f"data: {S['source']} | window {WINDOW} days, EWMA lambda {LAMBDA}, tail refit every {REFIT} days\n"]
    L.append("\n## Tail shape\n\n")
    L.append(lab.md_table([dict(asset=a, **v) for a, v in S["tail_shape"].items()]))
    L.append("\n_hill_alpha_left: Hill tail index on the 5% largest losses (below 4 = infinite kurtosis). "
             "Counts use returns scaled by EWMA volatility known the day before._\n")
    for a, res in S["backtests"].items():
        for q in LEVELS:
            L.append(f"\n## {a} - {q:.1%} VaR / ES\n\n")
            L.append(lab.md_table(res[str(q)]))
    L.append("\n_kupiec_p < 0.05: wrong number of breaches. christoffersen_p < 0.05: breaches cluster. "
             "es_realized_over_predicted > 1: losses beyond VaR worse than forecast; es_test_t > 2 is significant. "
             "basel_*: % of rolling 250-day windows in each zone._\n")
    with open(os.path.join(out, "tail_summary.md"), "w", encoding="utf-8") as f:
        f.write("".join(L))
    with open(os.path.join(out, "tail_summary.json"), "w", encoding="utf-8") as f:
        json.dump(S, f, indent=1, default=str)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--xs-start", default="2021-01-01")
    ap.add_argument("--cache", default="risk_cache")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.synthetic:
        data, _ = lab.synthetic_market()
    else:
        data = {}
        for c in lab.UNIVERSE:
            try:
                data[c] = lab.fetch_daily(c, a.start, a.cache)
            except Exception as e:
                print(f"skip {c}: {e}", flush=True)
    assets = build_assets(data, a.xs_start)
    S = dict(generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
             source="SYNTHETIC (test only)" if a.synthetic else "Binance daily candles",
             tail_shape={}, backtests={})
    results, btc_fc = {}, None
    for name, r in assets.items():
        print(f"{name}: {len(r)} days ...", flush=True)
        results[name] = {}
        S["backtests"][name] = {}
        sig = None
        for q in LEVELS:
            fc, sig, xi = forecast(r.values, q)
            rows = backtest(r.values, fc, sig, q, r.index)
            results[name][q] = rows
            S["backtests"][name][str(q)] = rows
            if name == "BTC" and q == 0.99:
                btc_fc = fc
        counts, T = tail_counts(r.values, sig)
        S["tail_shape"][name] = dict(days=len(r), first=str(r.index[0].date()), hill_alpha_left=round(hill_alpha(r.values), 2),
                                     gpd_xi_median=round(xi, 3), excess_kurtosis=round(float(stats.kurtosis(r)), 1),
                                     **{k: f"{v['actual']} (normal: {v['normal_expected']})" for k, v in counts.items()})
    chart_qq(assets["BTC"].values, a.out)
    chart_var_path(assets["BTC"].index, assets["BTC"].values, btc_fc, a.out)
    chart_ratios(results, a.out)
    chart_es(results, a.out)
    write_report(S, a.out)
    print(f"\nDone. New charts 10-13 and tail_summary.md in '{a.out}'", flush=True)


if __name__ == "__main__":
    main()
