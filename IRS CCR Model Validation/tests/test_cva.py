import numpy as np
from ccr_validation.curves import DiscountCurve
from ccr_validation.swaps import InterestRateSwap
from ccr_validation.hull_white import HullWhite1F
from ccr_validation.exposure import exposure_profile

from ccr_validation.cva import (
    ConstantHazardCreditModel,
    unilateral_cva,
)

times = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
discount_factors = [1.0, 0.981, 0.960, 0.918, 0.875, 0.795]
curve = DiscountCurve(times, discount_factors)

swap = InterestRateSwap(
    notional=10_000_000,
    fixed_rate=0.04,
    maturity=5.0,
    payments_per_year=2,
    pay_fixed=True,
)

hw = HullWhite1F(
    curve=curve,
    a=0.1,
    sigma=0.01,
)

profile = exposure_profile(
    swap=swap,
    model=hw,
    n_paths=100_000,
    seed=42,
)

def test_zero_hazard_gives_zero_cva():
    credit = ConstantHazardCreditModel(
        hazard_rate=0.0,
        recovery_rate=0.40,
    )

    cva = unilateral_cva(
        times=profile["times"],
        discounted_ee=profile["discounted_ee"],
        credit_model=credit,
    )

    assert np.isclose(cva, 0.0)


def test_full_recovery_gives_zero_cva():
    credit = ConstantHazardCreditModel(
        hazard_rate=0.02,
        recovery_rate=1.0,
    )

    cva = unilateral_cva(
        times=profile["times"],
        discounted_ee=profile["discounted_ee"],
        credit_model=credit,
    )

    assert np.isclose(cva, 0.0)


def test_higher_hazard_increases_cva():
    low_credit = ConstantHazardCreditModel(
        hazard_rate=0.01,
        recovery_rate=0.40,
    )

    high_credit = ConstantHazardCreditModel(
        hazard_rate=0.04,
        recovery_rate=0.40,
    )

    cva_low = unilateral_cva(
        profile["times"],
        profile["discounted_ee"],
        low_credit,
    )

    cva_high = unilateral_cva(
        profile["times"],
        profile["discounted_ee"],
        high_credit,
    )

    assert cva_high > cva_low
