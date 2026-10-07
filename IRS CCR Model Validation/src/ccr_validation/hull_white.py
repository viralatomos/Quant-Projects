from dataclasses import dataclass

import numpy as np

from numpy.typing import ArrayLike, NDArray
from .curves import DiscountCurve


@dataclass
class HullWhite1F:
    curve: DiscountCurve
    a: float
    sigma: float

    def __post_init__(self) -> None:
        if self.a <= 0:
            raise ValueError("a must be positive")

        if self.sigma < 0:
            raise ValueError("sigma must be non-negative")

    def phi(self, t: ArrayLike) -> np.ndarray:
        t = np.asarray(t, dtype=float)

        if np.any(t < 0):
            raise ValueError("t must be non-negative")

        f0t = self.curve.instantaneous_forward(t)

        convexity_adjustment = (
            self.sigma**2
            / (2.0 * self.a**2)
            * (1.0 - np.exp(-self.a * t))**2
        )

        return f0t + convexity_adjustment

    # ---------------------------------------
    # Path step: exact vs Euler-Maruyama
    # ---------------------------------------

    def exact_step(self, x_t: ArrayLike, dt: float, z: ArrayLike) -> NDArray[np.float64]:
        if dt <= 0.0:
            raise ValueError("dt must be positive")

        x_t = np.asarray(x_t, dtype=float)
        z = np.asarray(z, dtype=float)

        mean = x_t * np.exp(-self.a * dt)
        variance = self.sigma**2 / (2.0 * self.a) * (1.0 - np.exp(-2.0 * self.a * dt))

        return mean + np.sqrt(variance) * z


    def euler_step(self, x_t: ArrayLike, dt: float, z: ArrayLike) -> NDArray[np.float64]:
        if dt <= 0.0:
            raise ValueError("dt must be positive")

        x_t = np.asarray(x_t, dtype=float)
        z = np.asarray(z, dtype=float)

        # small dt approximation
        mean = (1.0 - self.a * dt) * x_t
        variance = self.sigma**2 * dt

        return mean + np.sqrt(variance) * z


    # ---------------------------------------
    # Path simulation
    # ---------------------------------------

    def simulate_x_paths(
        self,
        times: ArrayLike,
        n_paths: int,
        x0: float = 0.0,
        seed: int | None = None,
    ) -> NDArray[np.float64]:

        times = np.asarray(times, dtype=float)

        if times.ndim != 1:
            raise ValueError("times must be a 1D array")

        if not np.isclose(times[0], 0.0):
            raise ValueError("times must start at 0")

        if np.any(np.diff(times) <= 0):
            raise ValueError("times must be strictly increasing")

        if n_paths <= 0:
            raise ValueError("n_paths must be positive")

        rng = np.random.default_rng(seed)

        paths = np.empty((n_paths, len(times)), dtype=float)
        paths[:, 0] = x0

        for i in range(1, len(times)):
            dt = times[i] - times[i - 1]
            z = rng.standard_normal(n_paths)

            paths[:, i] = self.exact_step(x_t=paths[:, i - 1], dt=dt, z=z)

        return paths


    def simulate_x_paths_euler(
        self,
        times: ArrayLike,
        n_paths: int,
        x0: float = 0.0,
        seed: int | None = None,
    ) -> NDArray[np.float64]:

        times = np.asarray(times, dtype=float)

        if times.ndim != 1:
            raise ValueError("times must be a 1D array")

        if not np.isclose(times[0], 0.0):
            raise ValueError("times must start at 0")

        if np.any(np.diff(times) <= 0):
            raise ValueError("times must be strictly increasing")

        if n_paths <= 0:
            raise ValueError("n_paths must be positive")

        rng = np.random.default_rng(seed)

        paths = np.empty((n_paths, len(times)), dtype=float)
        paths[:, 0] = x0

        for i in range(1, len(times)):
            dt = times[i] - times[i - 1]
            z = rng.standard_normal(n_paths)

            paths[:, i] = self.euler_step(x_t=paths[:, i - 1], dt=dt, z=z)

        return paths

    def short_rate_paths(
        self,
        times: ArrayLike,
        n_paths: int,
        x0: float = 0.0,
        seed: int | None = None,
    ) -> NDArray[np.float64]:

        times = np.asarray(times, dtype=float)

        x_paths = self.simulate_x_paths(
            times=times,
            n_paths=n_paths,
            x0=x0,
            seed=seed,
        )

        phi_values = self.phi(times)

        return x_paths + phi_values

    # ---------------------------------------
    # Zero-coupon bond price
    # ---------------------------------------

    def B(self, t: float, T: float) -> float:
        if T < t:
            raise ValueError("T must be greater than or equal to t")

        return (1.0 - np.exp(-self.a * (T - t))) / self.a

    def A(self, t: float, T: float) -> float:
        if T < t:
            raise ValueError("T must be greater than or equal to t")

        B = self.B(t, T)

        P0T = float(self.curve.discount(T))
        P0t = float(self.curve.discount(t))
        f0t = float(self.curve.instantaneous_forward(t))

        convexity = (
            self.sigma**2 / (4.0 * self.a) * (1.0 - np.exp(-2.0 * self.a * t)) * B**2
        )

        return (P0T / P0t) * np.exp(B * f0t - convexity)

    def bond_price(self, t: float, T: float, x_t: ArrayLike) -> np.ndarray:
        x_t = np.asarray(x_t, dtype=float)

        r_t = x_t + self.phi(t)

        return self.A(t, T) * np.exp(-self.B(t, T) * r_t)