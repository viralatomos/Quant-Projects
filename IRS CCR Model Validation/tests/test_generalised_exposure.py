import numpy as np

from ccr_validation.curves import DiscountCurve
from ccr_validation.hull_white import HullWhite1F
from ccr_validation.swaps import InterestRateSwap
from ccr_validation.exposure import exposure_profile, _ois_accrual_factors


def flat_curve(rate: float = 0.05) -> DiscountCurve:
    times = np.array([0.0, 1.0, 5.0, 10.0])
    dfs = np.exp(-rate * times)
    return DiscountCurve(times, dfs)


def test_ois_accrual_resets_at_payment_dates():
    times = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    short_rates = np.full((2, len(times)), 0.05)

    factors = _ois_accrual_factors(
        times=times,
        short_rate_paths=short_rates,
        payment_times=np.array([0.5, 1.0]),
    )

    expected = np.array([
        1.0,
        np.exp(0.05 * 0.25),
        1.0,
        np.exp(0.05 * 0.25),
        1.0,
    ])

    assert np.allclose(factors[0], expected)


def test_general_pv_matches_reset_pv_at_payment_date():
    curve = flat_curve()
    model = HullWhite1F(curve=curve, a=0.1, sigma=0.01)
    swap = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=0.04,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=True,
    )

    t = 1.0
    x_t = np.array([-0.01, 0.0, 0.01])

    def discount(T: float):
        return model.bond_price(t=t, T=T, x_t=x_t)

    general = swap.pv_at_time(
        t=t,
        discount=discount,
        floating_accrual_factor=np.ones_like(x_t),
    )
    reset = swap.pv_at_reset(t=t, discount=discount)

    assert np.allclose(general, reset)


def test_monthly_exposure_grid_runs_to_zero_at_maturity():
    curve = flat_curve()
    model = HullWhite1F(curve=curve, a=0.1, sigma=0.01)
    swap = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=0.04,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=True,
    )

    profile = exposure_profile(
        swap=swap,
        model=model,
        n_paths=2_000,
        seed=42,
        exposure_dt=1.0 / 12.0,
        simulation_dt=1.0 / 52.0,
    )

    assert np.isclose(profile["times"][0], 0.0)
    assert np.isclose(profile["times"][-1], swap.maturity)
    assert np.allclose(profile["mtm"][:, -1], 0.0)
