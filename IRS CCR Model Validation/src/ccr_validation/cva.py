from dataclasses import dataclass
import numpy as np
from numpy.typing import ArrayLike


@dataclass
class ConstantHazardCreditModel:
    hazard_rate: float
    recovery_rate: float

    def __post_init__(self) -> None:
        if self.hazard_rate < 0:
            raise ValueError("hazard_rate must be non-negative")

        if not 0.0 <= self.recovery_rate <= 1.0:
            raise ValueError("recovery_rate must lie in [0, 1]")

    def survival_probability(self, t: ArrayLike) -> np.ndarray:
        t = np.asarray(t, dtype=float)

        if np.any(t < 0):
            raise ValueError("t must be non-negative")

        return np.exp(-self.hazard_rate * t)

    def default_probability(self, t_start: float, t_end: float) -> float:
        if t_end <= t_start:
            raise ValueError("t_end must be greater than t_start")

        return float(
            self.survival_probability(t_start)
            - self.survival_probability(t_end)
        )

# ---------------------------------------
# CVA
# ---------------------------------------

def unilateral_cva(
    times: ArrayLike,
    discounted_ee: ArrayLike,
    credit_model: ConstantHazardCreditModel,
) -> float:
    """Unilateral CVA from expected path-discounted exposure.

    Assumes default is independent of the market-risk paths.
    ``discounted_ee`` must already include pathwise discounting to time zero;
    no additional discount curve is applied. Uses right-endpoint default weights.
    """
    times = np.asarray(times, dtype=float)
    discounted_ee = np.asarray(discounted_ee, dtype=float)

    if times.ndim != 1 or discounted_ee.ndim != 1:
        raise ValueError("times and discounted_ee must be 1D arrays")

    if len(times) != len(discounted_ee):
        raise ValueError("times and discounted_ee must have the same length")

    if len(times) < 2:
        raise ValueError("at least two time points are required")

    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(discounted_ee)):
        raise ValueError("times and discounted_ee must be finite")

    if np.any(np.diff(times) <= 0.0):
        raise ValueError("times must be strictly increasing")

    if np.any(discounted_ee < 0.0):
        raise ValueError("discounted_ee must be non-negative")

    if not np.isclose(times[0], 0.0):
        raise ValueError("times must start at 0")

    lgd = 1.0 - credit_model.recovery_rate
    cva = 0.0

    for i in range(1, len(times)):
        dp = credit_model.default_probability(
            times[i - 1],
            times[i],
        )
        cva += discounted_ee[i] * dp

    return float(lgd * cva)
