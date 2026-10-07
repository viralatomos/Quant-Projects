import numpy as np
import pytest

from ccr_validation.curves import DiscountCurve
from ccr_validation.hull_white import HullWhite1F
from ccr_validation.swaps import InterestRateSwap
from ccr_validation.swaptions import hw_bond_option_price, hw_swaption_price
from ccr_validation.exposure import exposure_profile
from ccr_validation.cva import ConstantHazardCreditModel, unilateral_cva


def flat_curve(rate=0.04):
    times = np.array([0.0, 1.0, 5.0, 10.0])
    return DiscountCurve(times, np.exp(-rate * times))


@pytest.fixture(scope="module")
def stochastic_case():
    curve = flat_curve()
    model = HullWhite1F(curve, a=0.03, sigma=0.01)
    swap = InterestRateSwap(10_000_000, 0.0, 5.0, 1)
    swap.fixed_rate = swap.par_rate(curve)
    profile = exposure_profile(
        swap, model, 40_000, seed=123,
        exposure_dt=1 / 12, simulation_dt=1 / 104,
    )
    return curve, model, swap, profile


def test_deterministic_discounting_runs_through_coupon_dates():
    curve = flat_curve()
    model = HullWhite1F(curve, a=0.1, sigma=0.0)
    swap = InterestRateSwap(1_000_000, 0.03, 3.0, 1)
    profile = exposure_profile(
        swap, model, 2, exposure_dt=1 / 12, simulation_dt=1 / 52,
    )
    expected = curve.discount(profile["times"])
    assert np.allclose(profile["discount_factors"], expected, atol=1e-12)
    assert np.allclose(profile["discounted_ee"], expected * profile["ee"])


def test_expected_discount_factors_reproduce_initial_curve(stochastic_case):
    curve, _, _, profile = stochastic_case
    for t in [1.0, 3.0, 5.0]:
        i = np.flatnonzero(np.isclose(profile["times"], t))[0]
        samples = profile["discount_factors"][:, i]
        se = samples.std(ddof=1) / np.sqrt(len(samples))
        assert abs(samples.mean() - curve.discount(t)) < 5 * se + 2e-5


def test_reset_discounted_exposure_matches_analytic_swaption(stochastic_case):
    _, model, swap, profile = stochastic_case
    for t in [1.0, 2.0, 3.0]:
        i = np.flatnonzero(np.isclose(profile["times"], t))[0]
        payments = swap.payment_times[swap.payment_times > t]
        analytic = swap.notional * hw_swaption_price(
            model, t, payments, np.full(len(payments), swap.accrual),
            swap.fixed_rate, swap.pay_fixed,
        )
        samples = profile["discount_factors"][:, i] * profile["exposure"][:, i]
        se = samples.std(ddof=1) / np.sqrt(len(samples))
        assert abs(samples.mean() - analytic) < 5 * se + 10.0


def test_cva_does_not_discount_already_discounted_exposure():
    times = np.array([0.0, 1.0, 2.0])
    discounted_ee = np.array([0.0, 80.0, 50.0])
    credit = ConstantHazardCreditModel(0.02, 0.4)
    expected = 0.6 * np.dot(
        discounted_ee[1:], -np.diff(np.exp(-0.02 * times)),
    )
    assert unilateral_cva(times, discounted_ee, credit) == pytest.approx(expected)


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("strike", [0.5, 1.1])
def test_exact_zero_volatility_bond_option(option_type, strike):
    curve = flat_curve()
    model = HullWhite1F(curve, a=0.05, sigma=0.0)
    difference = curve.discount(5.0) - strike * curve.discount(1.0)
    expected = max(difference if option_type == "call" else -difference, 0.0)
    assert hw_bond_option_price(model, 1.0, 5.0, strike, option_type) == pytest.approx(expected)


def test_zero_volatility_still_rejects_invalid_option_type():
    model = HullWhite1F(flat_curve(), a=0.05, sigma=0.0)
    with pytest.raises(ValueError, match="option_type"):
        hw_bond_option_price(model, 1.0, 5.0, 0.8, "invalid")
