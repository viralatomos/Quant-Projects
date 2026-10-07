import numpy as np
from scipy.integrate import cumulative_trapezoid

from typing import Literal
from numpy.typing import ArrayLike, NDArray

from .hull_white import HullWhite1F
from .swaps import InterestRateSwap


def _regular_grid(maturity: float, dt: float) -> np.ndarray:
    if dt <= 0.0:
        raise ValueError("dt must be positive")

    grid = np.arange(0.0, maturity, dt)
    return np.append(grid, maturity)

def _merge_times(*time_arrays: ArrayLike) -> np.ndarray:
    merged = np.concatenate([np.asarray(times, dtype=float) for times in time_arrays])

    # Rounding prevents tiny floating-point differences from producing
    # duplicate economic dates such as 0.5 and 0.5000000000000001.
    return np.unique(np.round(merged, 12))

def _indices_on_grid(
    grid: np.ndarray,
    target_times: np.ndarray,
) -> np.ndarray:
    indices = []

    for t in target_times:
        matches = np.flatnonzero(np.isclose(grid, t, atol=1e-12, rtol=0.0))

        if len(matches) != 1:
            raise ValueError(f"Could not locate time {t} uniquely on simulation grid")

        indices.append(matches[0])

    return np.asarray(indices, dtype=int)

def _ois_accrual_factors(
    times: np.ndarray,
    short_rate_paths: NDArray[np.float64],
    payment_times: np.ndarray,
) -> NDArray[np.float64]:
    """Pathwise realised OIS accumulation since the latest payment date.

    The integral of the model short rate is approximated by the trapezoidal
    rule on ``times``. Values at payment dates use a post-payment convention,
    so the accumulation factor is reset to 1 immediately after the cashflow.
    """
    if short_rate_paths.shape[1] != len(times):
        raise ValueError("short_rate_paths and times have incompatible shapes")

    factors = np.ones_like(short_rate_paths, dtype=float)
    log_accrual = np.zeros(short_rate_paths.shape[0], dtype=float)

    for i in range(1, len(times)):
        dt = times[i] - times[i - 1]

        log_accrual += 0.5 * (short_rate_paths[:, i - 1] + short_rate_paths[:, i]) * dt

        if np.any(np.isclose(times[i], payment_times, atol=1e-12, rtol=0.0)):
            # The coupon ending here has just been paid. Start the next
            # accrual period from one.
            log_accrual[:] = 0.0
            factors[:, i] = 1.0
        else:
            factors[:, i] = np.exp(log_accrual)

    return factors

def exposure_profile(
    swap: InterestRateSwap,
    model: HullWhite1F,
    n_paths: int,
    pfe_quantiles: tuple[float, ...] = (0.95, 0.99),
    seed: int | None = None,
    simulation_method: Literal["exact", "euler"] = "exact",
    exposure_dt: float | None = None,
    simulation_dt: float | None = None,
) -> dict[str, NDArray[np.float64]]:
    """Simulate future OIS swap exposure on reset or arbitrary time grids.

    ``exposure_dt=None`` preserves the previous reset/payment-date profile.
    Otherwise exposures are reported on a regular grid with spacing
    ``exposure_dt``. Contractual payment dates are always included.

    ``simulation_dt`` controls the grid used both for Hull-White simulation
    and numerical integration of realised OIS accrual. It may be finer than
    the exposure grid.

    ``ee`` and PFE are undiscounted risk-neutral exposure statistics.
    ``discounted_ee`` averages exposure multiplied by the discount factor
    integrated along the same path from time zero. That integral never resets
    at coupon dates and uses trapezoidal integration, even with exact OU steps.
    """
    if exposure_dt is None:
        exposure_times = _merge_times(
            np.array([0.0]),
            swap.payment_times,
        )
    else:
        exposure_times = _merge_times(
            _regular_grid(swap.maturity, exposure_dt),
            swap.payment_times,
        )

    if simulation_dt is None:
        simulation_times = exposure_times
    else:
        simulation_times = _merge_times(
            _regular_grid(swap.maturity, simulation_dt),
            exposure_times,
            swap.payment_times,
        )

    if simulation_method == "exact":
        x_paths_full = model.simulate_x_paths(
            times=simulation_times,
            n_paths=n_paths,
            seed=seed,
        )
    elif simulation_method == "euler":
        x_paths_full = model.simulate_x_paths_euler(
            times=simulation_times,
            n_paths=n_paths,
            seed=seed,
        )
    else:
        raise ValueError("simulation_method must be 'exact' or 'euler'")

    short_rate_paths_full = (
        x_paths_full
        + np.asarray(model.phi(simulation_times))[None, :]
    )

    floating_accrual_full = _ois_accrual_factors(
        times=simulation_times,
        short_rate_paths=short_rate_paths_full,
        payment_times=swap.payment_times,
    )

    exposure_indices = _indices_on_grid(
        simulation_times,
        exposure_times,
    )

    x_paths = x_paths_full[:, exposure_indices]
    floating_accrual = floating_accrual_full[:, exposure_indices]

    mtm = np.zeros_like(x_paths)

    for i, t in enumerate(exposure_times):
        if np.isclose(t, swap.maturity):
            mtm[:, i] = 0.0
            continue

        x_t = x_paths[:, i]

        def discount(T: float) -> NDArray[np.float64]:
            return model.bond_price(
                t=t,
                T=T,
                x_t=x_t,
            )

        mtm[:, i] = swap.pv_at_time(
            t=t,
            discount=discount,
            floating_accrual_factor=floating_accrual[:, i],
        )

    exposure = np.maximum(mtm, 0.0)
    ee = np.mean(exposure, axis=0)

    # Integrate from time zero without resetting at payment dates.
    integrated_rates = cumulative_trapezoid(
        short_rate_paths_full,
        x=simulation_times,
        axis=1,
        initial=0.0,
    )

    discount_factors = np.exp(-integrated_rates[:, exposure_indices])

    discounted_ee = np.mean(discount_factors * exposure, axis=0)

    result = {
        "times": exposure_times,
        "mtm": mtm,
        "exposure": exposure,
        "ee": ee,
        "discounted_ee": discounted_ee,
        "discount_factors": discount_factors,
    }

    for q in pfe_quantiles:
        result[f"pfe_{int(q * 100)}"] = np.quantile(exposure, q, axis=0)

    return result
