# Residual Structure After Factor Neutralization in Equity Returns

## Overview

This project studies whether the component of stock returns left unexplained by standard factor models still contains simple cross-sectional information about future returns.

The core question is:

> After removing standard factor-driven structure from stock returns, does the remaining residual component still predict future returns out of sample?

The goal is not to maximize backtest performance with complex models. The goal is to build a clean first empirical asset pricing / quant research project with careful data handling, simple methods, and honest interpretation.

---

## Main Result

The main finding is cautious:

- A mild residual-reversal pattern appears under FF3
- That effect weakens materially under FF5
- Lagged FF5 residual-reversal variants are not convincing
- Simple residual momentum shows little evidence
- Winsorizing forward returns does not materially change the conclusion

Overall, I find limited evidence for a robust, persistent mean-reverting residual component in monthly stock returns once a richer factor model is used.

---

## Research Question and Motivation

A lot of apparent cross-sectional return predictability may reflect known systematic factor structure rather than genuinely stock-specific information.

This project asks whether, after neutralizing monthly stock returns using rolling factor exposures, the remaining residual return still contains usable predictive information for next-month returns.

This is a deliberately simple and conservative setup:
- no machine learning
- no complex alpha combinations
- no aggressive optimization

Instead, the emphasis is on:
- point-in-time universe construction
- lagged estimation
- simple signal definitions
- clean out-of-sample evaluation
- realistic interpretation of weak results

---

## Data

### Universe
- U.S. equities
- Monthly horizon
- Liquid universe only

### Price data
- Source: Stooq daily stock data
- Close prices appear split-adjusted
- Prices do **not** appear dividend-adjusted
- Returns in this project are therefore **monthly price returns**, not total returns

### Monthly universe definition
For each month, the universe is defined point-in-time as:
- top 1500 U.S. stocks by trailing 60-trading-day median dollar volume
- month-end snapshot uses the last available trading day of the month
- stock becomes eligible only after at least 60 prior valid daily observations

### Factor data
- Fama-French 3-factor data
- Fama-French 5-factor data
- Monthly risk-free rate used to construct excess returns

---

## Panel Construction

I built a monthly stock panel where each row corresponds to a stock-month observation, including:

- `ticker`
- `month`
- `month_end_date`
- `month_end_close`
- `ret_1m`: realized return from month \( t-1 \) to \( t \)
- `ret_fwd_1m`: forward return from month \( t \) to \( t+1 \)

This panel is the base dataset for factor neutralization and signal testing.

---

## Methodology

### 1. Excess return construction

For each stock-month:

\[
\text{excess\_ret\_1m}_{i,t} = \text{ret\_1m}_{i,t} - rf_t
\]

where \( rf_t \) is the monthly risk-free rate.

### 2. Rolling beta estimation

For each stock, I estimated rolling time-series factor betas using:
- monthly returns
- trailing 36-month window
- minimum 24 valid observations
- coefficients estimated using data through month \( t-1 \)

This ensures factor exposures used at month \( t \) are based only on information available at the time.

### 3. Residual construction

Using estimated betas and realized month-\( t \) factor returns, I decomposed monthly excess return into:
- factor-explained component
- residual component

Conceptually:

\[
\text{excess return} = \text{fitted factor component} + \text{residual}
\]

The residual is the main object of interest.

---

## Signals Tested

### FF3 residual-based signals

#### Residual reversal
- Signal = negative of current FF3 residual
- Intuition: stocks with very negative residual shocks may bounce next month

#### Residual momentum
- Signal = 6-month trailing sum of lagged FF3 residuals
- Intuition: persistent residual strength may continue

### FF5 residual-based signals

#### Contemporaneous residual reversal
- Signal = negative of current FF5 residual

#### Lagged 1-month residual reversal
- Signal based on prior month’s FF5 residual

#### Lagged 3-month average residual reversal
- Signal based on average lagged FF5 residual over the prior 3 months

### Robustness check
- Forward returns winsorized cross-sectionally within each month at 1% / 99%

---

## Evaluation

I used two primary evaluation methods.

### 1. Monthly rank IC
For each month, I computed the cross-sectional Spearman rank correlation between:
- signal at month \( t \)
- forward return at month \( t+1 \)

This measures whether higher-ranked signals tend to be followed by higher next-month returns.

### 2. Monthly quintile sorts
For each month:
- stocks are sorted into 5 buckets by signal
- equal-weight next-month return is computed for each bucket
- focus is on the spread: **Q5 - Q1**

I also imposed minimum cross-sectional count thresholds by month to avoid unstable IC estimates.

---

## Results

### FF3
- Residual reversal looked mildly promising
- It outperformed raw 1-month reversal on a matched month sample
- Residual momentum looked weak / near noise
### FF5
- Residual reversal weakened materially under FF5
- It remained only slightly better than raw reversal
- Lagged 1-month FF5 residual reversal was essentially absent
- Lagged 3-month average FF5 residual reversal was also unconvincing

### Winsorized-target robustness
- Winsorizing forward returns did not materially change the overall conclusion

---

## Interpretation

The clean takeaway is:

> A mild residual-reversal pattern appears under FF3, but it weakens materially under FF5 and disappears in lagged FF5 tests. Simple residual momentum also shows no evidence. Overall, there is limited evidence for a robust, persistent mean-reverting residual component in monthly stock returns once a richer factor model is used.

One interpretation is that FF3 residuals may still contain omitted systematic structure that FF5 captures more fully. If so, the FF3 residual-reversal effect may not reflect a truly robust idiosyncratic signal.

---

## Limitations

This project has several important limitations:

- Stooq prices appear not to be dividend-adjusted, so returns are price returns rather than total returns
- Rolling stock-level beta estimates are noisy, especially with limited monthly history
- Results depend on the chosen factor model
- Only the monthly horizon is studied
- Quintile sorts are equal-weighted and do not directly address implementation frictions
- No transaction cost or turnover analysis is included
- This is a first-pass empirical study rather than a production-grade backtest

---

## Project Structure

```text
.
├── README.md
├── 01_stooq_panel_construction.ipynb
├── 02_factor_merge_and_rolling_betas.ipynb
├── 03_residual_signal_analysis.ipynb
├── ff data
│   ├── F-F_Research_Data_Factors.csv
│   └── F-F_Research_Data_5_Factors_2x3.csv
├── parquets
│   ├── daily_prices_stooq.parquet
│   ├── monthly_top1500_and_ff3.parquet
│   ├── monthly_top1500_and_ff5.parquet 
│   └── monthly_top1500_liquidity.parquet
└── requirements.txt