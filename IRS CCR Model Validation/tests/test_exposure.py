import numpy as np
from ccr_validation.curves import DiscountCurve
from ccr_validation.swaps import InterestRateSwap
from ccr_validation.hull_white import HullWhite1F
from ccr_validation.exposure import exposure_profile


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

def test_exposure_is_non_negative():
    profile = exposure_profile(
        swap=swap,
        model=hw,
        n_paths=20_000,
        seed=42,
    )

    assert np.all(profile["exposure"] >= 0.0)


def test_pfe_quantile_ordering():
    profile = exposure_profile(
        swap=swap,
        model=hw,
        n_paths=20_000,
        seed=42,
    )

    assert np.all(
        profile["pfe_99"] >= profile["pfe_95"]
    )


def test_exposure_zero_at_maturity():
    profile = exposure_profile(
        swap=swap,
        model=hw,
        n_paths=20_000,
        seed=42,
    )

    assert np.isclose(profile["ee"][-1], 0.0)
    assert np.isclose(profile["pfe_95"][-1], 0.0)
    assert np.isclose(profile["pfe_99"][-1], 0.0)