from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .curves import DiscountCurve
from .hull_white import HullWhite1F
from .swaps import (
    fixed_leg_schedule,
    swap_annuity,
)
from .swaptions import (
    black_implied_vol,
    hw_swaption_price,
)


def price_calibration_row(
    row: pd.Series,
    model: HullWhite1F,
    market_date: pd.Timestamp,
) -> float:
    """
    Hull-White price per unit notional for one calibration-basket row.
    """

    expiry_date = row["First exercise date"]
    maturity_date = row["Maturity date of the underlier"]

    S = (expiry_date - market_date).days / 365.0

    payment_dates, accruals = fixed_leg_schedule(expiry_date, maturity_date)

    payment_times = np.array([(date - market_date).days / 365.0 for date in payment_dates])

    return hw_swaption_price(
        model=model,
        option_expiry=S,
        payment_times=payment_times,
        accruals=accruals,
        fixed_rate=row["strike"],
        payer=bool(row["payer"]),
    )


def calibration_row_annuity(
    row: pd.Series,
    curve: DiscountCurve,
    market_date: pd.Timestamp,
) -> float:
    """
    Fixed-leg annuity for one calibration-basket row.
    """

    return swap_annuity(
        curve=curve,
        market_date=market_date,
        start_date=row["First exercise date"],
        maturity_date=row["Maturity date of the underlier"],
    )


def add_market_black_vols(
    calibration_basket: pd.DataFrame,
    curve: DiscountCurve,
    market_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Return a copy of the calibration basket with annuity and
    market Black implied volatility columns added.
    """

    basket = calibration_basket.copy()

    basket["annuity"] = basket.apply(
        lambda row: calibration_row_annuity(
            row=row,
            curve=curve,
            market_date=market_date,
        ),
        axis=1,
    )

    basket["market_black_vol"] = basket.apply(
        lambda row: black_implied_vol(
            price=row["premium_per_notional"],
            forward=row["forward_rate"],
            strike=row["strike"],
            expiry=row["option_expiry_years"],
            annuity=row["annuity"],
            payer=bool(row["payer"]),
        ),
        axis=1,
    )

    return basket


def relative_premium_residuals(
    log_params: np.ndarray,
    curve: DiscountCurve,
    calibration_basket: pd.DataFrame,
    market_date: pd.Timestamp,
) -> np.ndarray:
    """
    Relative premium residuals used for the baseline calibration.
    """

    a, sigma = np.exp(log_params)

    model = HullWhite1F(
        curve=curve,
        a=a,
        sigma=sigma,
    )

    model_prices = calibration_basket.apply(
        lambda row: price_calibration_row(
            row=row,
            model=model,
            market_date=market_date,
        ),
        axis=1,
    ).to_numpy()

    market_prices = calibration_basket["premium_per_notional"].to_numpy()

    return (model_prices - market_prices) / market_prices


def hw_implied_black_vol(
    row: pd.Series,
    model: HullWhite1F,
    market_date: pd.Timestamp,
) -> float:
    """
    Black implied volatility of the Hull-White model price
    for one calibration-basket row.
    """

    model_price = price_calibration_row(
        row=row,
        model=model,
        market_date=market_date,
    )

    return black_implied_vol(
        price=model_price,
        forward=row["forward_rate"],
        strike=row["strike"],
        expiry=row["option_expiry_years"],
        annuity=row["annuity"],
        payer=bool(row["payer"]),
    )


def vol_calibration_residuals(
    log_params: np.ndarray,
    curve: DiscountCurve,
    calibration_basket: pd.DataFrame,
    market_date: pd.Timestamp,
) -> np.ndarray:
    """
    Black implied-volatility residuals for (a, sigma).
    """

    a, sigma = np.exp(log_params)

    model = HullWhite1F(
        curve=curve,
        a=a,
        sigma=sigma,
    )

    model_vols = calibration_basket.apply(
        lambda row: hw_implied_black_vol(
            row=row,
            model=model,
            market_date=market_date,
        ),
        axis=1,
    ).to_numpy()

    market_vols = calibration_basket["market_black_vol"].to_numpy()

    return model_vols - market_vols


def fit_sigma_for_fixed_a(
    a: float,
    curve: DiscountCurve,
    calibration_basket: pd.DataFrame,
    market_date: pd.Timestamp,
    initial_sigma: float = 0.008,
    sigma_bounds: tuple[float, float] | None = None,
) -> tuple[float, float]:
    """
    Re-optimise sigma for a fixed Hull-White mean-reversion parameter.

    Returns
    -------
    sigma_best:
        Profile-optimal sigma at the supplied a.

    rms_vol_error:
        RMS Black implied-volatility residual at the optimum.
    """

    if a <= 0.0:
        raise ValueError("a must be positive.")

    if initial_sigma <= 0.0:
        raise ValueError("initial_sigma must be positive.")

    required_columns = {"market_black_vol", "annuity"}

    missing = required_columns - set(calibration_basket.columns)

    if missing:
        raise ValueError("Calibration basket is missing required " f"columns: {sorted(missing)}")

    def sigma_residual(log_sigma: np.ndarray) -> np.ndarray:

        sigma = np.exp(log_sigma[0])

        model = HullWhite1F(
            curve=curve,
            a=a,
            sigma=sigma,
        )

        model_vols = calibration_basket.apply(
            lambda row: hw_implied_black_vol(
                row=row,
                model=model,
                market_date=market_date,
            ),
            axis=1,
        ).to_numpy()

        market_vols = calibration_basket["market_black_vol"].to_numpy()

        return model_vols - market_vols

    if sigma_bounds is None:
        bounds = (-np.inf, np.inf,)
    else:
        lower, upper = sigma_bounds

        if (lower <= 0.0 or upper <= lower):
            raise ValueError("sigma_bounds must satisfy 0 < lower < upper.")

        bounds = (
            np.log([lower]),
            np.log([upper]),
        )

    fit = least_squares(
        sigma_residual,
        x0=np.log([initial_sigma]),
        bounds=bounds,
        xtol=1e-12,
        ftol=1e-12,
        gtol=1e-12,
        max_nfev=5000,
    )

    sigma_best = float(np.exp(fit.x[0]))

    residuals = sigma_residual(np.log([sigma_best]))

    rms_vol_error = float(np.sqrt(np.mean(residuals**2)))

    return sigma_best, rms_vol_error


def fit_hull_white_black_vol(
    curve: DiscountCurve,
    calibration_basket: pd.DataFrame,
    market_date: pd.Timestamp,
    initial_guess: tuple[float, float] = (
        0.05,
        0.01,
    ),
) -> tuple[float, float, float]:
    """
    Fit both a and sigma using Black implied-volatility residuals.

    Returns
    -------
    a_best, sigma_best, rms_vol_error
    """

    a0, sigma0 = initial_guess

    if a0 <= 0.0 or sigma0 <= 0.0:
        raise ValueError("initial_guess values must be positive.")

    fit = least_squares(
        vol_calibration_residuals,
        x0=np.log([
            a0,
            sigma0,
        ]),
        args=(
            curve,
            calibration_basket,
            market_date,
        ),
        xtol=1e-12,
        ftol=1e-12,
        gtol=1e-12,
        max_nfev=5000,
    )

    a_best, sigma_best = np.exp(fit.x)

    residuals = vol_calibration_residuals(
        fit.x,
        curve,
        calibration_basket,
        market_date,
    )

    rms_vol_error = float(np.sqrt(np.mean(residuals**2)))

    return (
        float(a_best),
        float(sigma_best),
        rms_vol_error,
    )
