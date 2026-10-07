import numpy as np

from ccr_validation.curves import DiscountCurve
from ccr_validation.swaps import InterestRateSwap


times = np.array([0.0, 0.5, 1.0, 2.0, 3.0, 5.0])
discounts = np.array([1.0, 0.981, 0.960, 0.918, 0.875, 0.795])

curve = DiscountCurve(times, discounts)


def test_payment_schedule():
    swap = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=0.04,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=True,
    )

    expected = np.arange(0.5, 5.0 + 0.5, 0.5)

    assert np.allclose(swap.payment_times, expected)


def test_par_swap_has_zero_pv():
    template = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=0.04,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=True,
    )

    par_rate = template.par_rate(curve)

    par_swap = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=par_rate,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=True,
    )

    assert np.isclose(par_swap.pv(curve), 0.0, atol=1e-8)


def test_payer_receiver_have_opposite_pv():
    payer = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=0.04,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=True,
    )

    receiver = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=0.04,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=False,
    )

    assert np.isclose(
        payer.pv(curve),
        -receiver.pv(curve),
    )


def test_pay_fixed_below_par_has_positive_pv():
    swap = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=0.04,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=True,
    )

    assert swap.fixed_rate < swap.par_rate(curve)
    assert swap.pv(curve) > 0.0


def test_pay_fixed_has_positive_parallel_pv01():
    swap = InterestRateSwap(
        notional=10_000_000,
        fixed_rate=0.04,
        maturity=5.0,
        payments_per_year=2,
        pay_fixed=True,
    )

    bumped_curve = curve.parallel_bump(1.0)

    pv01 = swap.pv(bumped_curve) - swap.pv(curve)

    assert pv01 > 0.0