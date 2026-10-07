import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import PchipInterpolator


class DiscountCurve:
    def __init__(
        self, 
        times: ArrayLike, 
        discount_factors: ArrayLike,
    ) -> None:
        self.times = np.asarray(times, dtype=float)
        self.discount_factors = np.asarray(discount_factors, dtype=float)

        if self.times.ndim != 1 or self.discount_factors.ndim != 1:
            raise ValueError("times and discount_factors must be 1D arrays")

        if len(self.times) != len(self.discount_factors):
            raise ValueError("times and discount_factors must have the same length")

        if np.any(np.diff(self.times) <= 0):
            raise ValueError("times must be strictly increasing")

        if np.any(self.discount_factors <= 0):
            raise ValueError("discount factors must be positive")

        if not np.isclose(self.times[0], 0.0):
            raise ValueError("curve must start at T = 0")

        if not np.isclose(self.discount_factors[0], 1.0):
            raise ValueError("P(0,0) must equal 1")

        self._log_discount_interp = PchipInterpolator(
            self.times,
            np.log(self.discount_factors),
        )
        
        self._log_discount_derivative = self._log_discount_interp.derivative()

    # ---------------------------------------
    # Discount and forward rates
    # ---------------------------------------

    def discount(self, T: ArrayLike) -> np.ndarray:            
        return np.exp(self._log_discount_interp(T))

    def zero_rate(self, T: ArrayLike) -> np.ndarray:
        T = np.asarray(T, dtype=float)

        if np.any(T < 0):
            raise ValueError("T must be non-negative")

        P = self.discount(T)

        # R(0,T) = -log(P(0,T)) / T
        # At T = 0 the expression is 0/0, so handle separately.
        return np.where(np.isclose(T, 0.0), 0.0, -np.log(P) / T)

    def forward_rate(self, T1: float, T2: float) -> float:
        if T1 < 0:
            raise ValueError("T1 must be non-negative")

        if T2 <= T1:
            raise ValueError("T2 must be greater than T1")

        P1 = self.discount(T1)
        P2 = self.discount(T2)

        alpha = T2 - T1

        return float((P1 / P2 - 1.0) / alpha)

    def instantaneous_forward(self, T: ArrayLike) -> np.ndarray:
        T = np.asarray(T, dtype=float)

        if np.any(T < self.times[0]) or np.any(T > self.times[-1]):
            raise ValueError("T is outside the curve range")

        return -self._log_discount_derivative(T)

    # ---------------------------------------
    # Bump for PV01
    # ---------------------------------------

    def parallel_bump(self, bump_bp: float) -> "DiscountCurve":
        bump = bump_bp * 1e-4

        bumped_discounts = (
            self.discount_factors * np.exp(-bump * self.times)
        )

        return DiscountCurve(self.times, bumped_discounts)