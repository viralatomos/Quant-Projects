import numpy as np
from ccr_validation.curves import DiscountCurve


times = np.array([0.0, 0.5, 1.0, 2.0, 3.0, 5.0])
discounts = np.array([1.0, 0.981, 0.960, 0.918, 0.875, 0.795])

curve = DiscountCurve(times, discounts)


def test_discount_nodes():
    for T, P in zip(times, discounts):
        assert np.isclose(curve.discount(T), P)


def test_zero_rate_round_trip():
    for T in times[1:]:
        R = curve.zero_rate(T)
        P_reconstructed = np.exp(-R * T)

        assert np.isclose(P_reconstructed, curve.discount(T))


def test_forward_rate_identity():
    T1, T2 = 1.0, 2.0

    F = curve.forward_rate(T1, T2)

    lhs = 1.0 + (T2 - T1) * F
    rhs = curve.discount(T1) / curve.discount(T2)

    assert np.isclose(lhs, rhs)


def test_instantaneous_forward_is_finite():
    for T in times:
        assert np.isfinite(curve.instantaneous_forward(T))