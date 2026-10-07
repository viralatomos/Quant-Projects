from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

from .hull_white import HullWhite1F


def hw_bond_option_price(
    model: HullWhite1F,
    option_expiry: float,
    bond_maturity: float,
    strike: float,
    option_type: str,
) -> float:
    """
    Time-0 price of a European option on a zero-coupon bond
    under Hull-White 1F.

    The option expires at S and the underlying bond matures at T > S.
    """

    S = option_expiry
    T = bond_maturity

    if S <= 0.0:
        raise ValueError("Option expiry must be positive.")

    if T <= S:
        raise ValueError("Bond maturity must exceed option expiry.")

    if strike <= 0.0:
        raise ValueError("Bond-option strike must be positive.")

    P0S = model.curve.discount(S)
    P0T = model.curve.discount(T)

    a = model.a
    sigma = model.sigma

    B_ST = model.B(S, T)

    if abs(a) < 1e-12:
        variance_factor = S
    else:
        variance_factor = (1.0 - np.exp(-2.0 * a * S)) / (2.0 * a)

    sigma_p = sigma * B_ST * np.sqrt(variance_factor)

    # Deterministic limiting case.
    if sigma_p < 1e-14:
        if option_type == "call":
            return float(max(P0T - strike * P0S, 0.0))
        if option_type == "put":
            return float(max(strike * P0S - P0T, 0.0))
        raise ValueError("option_type must be 'call' or 'put'.")

    h = np.log(P0T / (strike * P0S)) / sigma_p + 0.5 * sigma_p

    if option_type == "call":
        call = P0T * norm.cdf(h) - strike * P0S * norm.cdf(h - sigma_p)
        return float(call)

    if option_type == "put":
        put = strike * P0S * norm.cdf(-h + sigma_p) - P0T * norm.cdf(-h)
        return float(put)

    raise ValueError("option_type must be 'call' or 'put'.")


def hw_swaption_price(
    model: HullWhite1F,
    option_expiry: float,
    payment_times: np.ndarray,
    accruals: np.ndarray,
    fixed_rate: float,
    payer: bool,
) -> float:
    """
    Time-0 European swaption price per unit notional using
    Jamshidian decomposition.

    The underlying swap starts at option_expiry.

    payer=True:
        option to pay fixed / receive floating.

    payer=False:
        option to receive fixed / pay floating.
    """

    S = option_expiry

    payment_times = np.asarray(payment_times, dtype=float)

    accruals = np.asarray(accruals, dtype=float)

    if len(payment_times) != len(accruals):
        raise ValueError("payment_times and accruals must have equal length.")

    if np.any(payment_times <= S):
        raise ValueError("All swap payments must occur after option expiry.")

    # Receiver swap value at expiry:
    # K Σ alpha_i P(S,T_i) + P(S,T_n) - 1 = Σ c_i P(S,T_i) - 1
    cashflow_coeffs = fixed_rate * accruals
    cashflow_coeffs[-1] += 1.0

    def root_equation(x: float) -> float:
        bond_prices = np.array([model.bond_price(S, T, x) for T in payment_times])

        return np.dot(cashflow_coeffs, bond_prices) - 1.0

    lower = -0.05
    upper = 0.05

    f_lower = root_equation(lower)
    f_upper = root_equation(upper)

    for _ in range(50):
        if f_lower * f_upper <= 0.0:
            break

        lower *= 2.0
        upper *= 2.0

        f_lower = root_equation(lower)
        f_upper = root_equation(upper)
    else:
        raise RuntimeError("Could not bracket Jamshidian root.")

    x_star = brentq(
        root_equation,
        lower,
        upper,
    )

    bond_strikes = np.array([model.bond_price(S, T, x_star) for T in payment_times])

    option_type = "put" if payer else "call"

    bond_option_prices = np.array([
        hw_bond_option_price(
            model=model,
            option_expiry=S,
            bond_maturity=T,
            strike=K_bond,
            option_type=option_type,
        )
        for T, K_bond in zip(payment_times, bond_strikes)
    ])

    price = np.dot(cashflow_coeffs, bond_option_prices)

    return float(price)


def black_swaption_price(
    forward: float,
    strike: float,
    expiry: float,
    annuity: float,
    vol: float,
    payer: bool,
) -> float:
    """
    Black-76 European swaption price per unit notional.
    """

    if expiry <= 0.0:
        raise ValueError("Expiry must be positive.")

    if forward <= 0.0 or strike <= 0.0:
        raise ValueError("Black-76 requires positive forward and strike.")

    if vol <= 0.0:
        intrinsic = annuity * max(forward - strike if payer else strike - forward, 0.0)

        return float(intrinsic)

    vol_sqrt_t = vol * np.sqrt(expiry)

    d1 = np.log(forward / strike) / vol_sqrt_t + 0.5 * vol_sqrt_t
    d2 = d1 - vol_sqrt_t

    if payer:
        price = annuity * (forward * norm.cdf(d1) - strike * norm.cdf(d2))
    else:
        price = annuity * (strike * norm.cdf(-d2) - forward * norm.cdf(-d1))

    return float(price)


def black_implied_vol(
    price: float,
    forward: float,
    strike: float,
    expiry: float,
    annuity: float,
    payer: bool,
) -> float:
    """
    Black-76 implied volatility corresponding to a swaption price.
    """

    intrinsic = annuity * max(forward - strike if payer else strike - forward, 0.0)

    if price < intrinsic - 1e-12:
        raise ValueError("Option price is below intrinsic value.")

    def objective(vol: float) -> float:
        return (
            black_swaption_price(
                forward=forward,
                strike=strike,
                expiry=expiry,
                annuity=annuity,
                vol=vol,
                payer=payer,
            )
            - price
        )

    return float(
        brentq(
            objective,
            1e-8,
            5.0,
        )
    )
