import numpy as np
import pandas as pd
from numpy.typing import ArrayLike
from collections.abc import Callable
from dataclasses import dataclass

from .curves import DiscountCurve


def fixed_leg_schedule(
    start_date: pd.Timestamp,
    maturity_date: pd.Timestamp,
) -> tuple[list[pd.Timestamp], np.ndarray]:
    payment_dates = []

    next_date = start_date + pd.DateOffset(years=1)

    while next_date < maturity_date:
        payment_dates.append(next_date)
        next_date += pd.DateOffset(years=1)

    payment_dates.append(maturity_date)

    accruals = []
    previous_date = start_date

    for payment_date in payment_dates:
        accruals.append((payment_date - previous_date).days / 360.0)
        previous_date = payment_date

    return payment_dates, np.asarray(accruals)

def swap_annuity(
    curve: DiscountCurve,
    market_date: pd.Timestamp,
    start_date: pd.Timestamp,
    maturity_date: pd.Timestamp,
) -> float:
    payment_dates, accruals = fixed_leg_schedule(start_date, maturity_date)

    payment_times = np.array([
        (date - market_date).days / 365.0
        for date in payment_dates
    ])

    return float(np.sum(accruals * curve.discount(payment_times)))

def forward_ois_rate(
    curve: DiscountCurve,
    market_date: pd.Timestamp,
    start_date: pd.Timestamp,
    maturity_date: pd.Timestamp,
) -> float:
    payment_dates, accruals = fixed_leg_schedule(start_date, maturity_date)

    start_time = (start_date - market_date).days / 365.0

    payment_times = np.array([
        (date - market_date).days / 365.0
        for date in payment_dates
    ])

    df_start = curve.discount(start_time)
    payment_dfs = curve.discount(payment_times)

    return float(
        (df_start - payment_dfs[-1])
        / np.sum(accruals * payment_dfs)
    )


@dataclass
class InterestRateSwap:
    notional: float
    fixed_rate: float
    maturity: float
    payments_per_year: int
    pay_fixed: bool = True

    @property
    def accrual(self) -> float:
        return 1.0 / self.payments_per_year

    @property
    def payment_times(self) -> np.ndarray:
        n_payments = int(round(self.maturity * self.payments_per_year))
        return np.arange(1, n_payments + 1) * self.accrual

    def fixed_leg_pv(self, curve: DiscountCurve) -> float:
        return (
            self.notional
            * self.fixed_rate
            * self.accrual
            * np.sum(curve.discount(self.payment_times))
        )

    def floating_leg_pv(self, curve: DiscountCurve) -> float:
        # Spot-starting OIS in the single-curve framework.
        return self.notional * (1.0 - curve.discount(self.maturity))

    def par_rate(self, curve: DiscountCurve) -> float:
        annuity = self.accrual * np.sum(curve.discount(self.payment_times))
        return (1.0 - curve.discount(self.maturity)) / annuity

    def pv(self, curve: DiscountCurve) -> float:
        pv_fixed = self.fixed_leg_pv(curve)
        pv_float = self.floating_leg_pv(curve)

        if self.pay_fixed:
            return pv_float - pv_fixed

        return pv_fixed - pv_float

    def pv_at_time(
        self,
        t: float,
        discount: Callable[[float], ArrayLike],
        floating_accrual_factor: ArrayLike,
    ) -> np.ndarray:
        """Value the remaining OIS immediately after any cashflow at time ``t``.

        ``floating_accrual_factor`` is the realised OIS accumulation from the
        most recent payment date up to ``t``. At a payment date, under the
        post-payment convention used here, it is reset to 1.
        """
        if t < 0.0 or t > self.maturity:
            raise ValueError("t must lie within the swap lifetime")

        floating_accrual_factor = np.asarray(floating_accrual_factor, dtype=float)

        if np.any(floating_accrual_factor <= 0.0):
            raise ValueError("floating_accrual_factor must be positive")

        if np.isclose(t, self.maturity):
            return np.zeros_like(floating_accrual_factor, dtype=float)

        # Post-payment convention: a coupon at exactly t has already been paid.
        remaining_times = self.payment_times[self.payment_times > t]

        fixed_leg = (
            self.notional
            * self.fixed_rate
            * self.accrual
            * sum(np.asarray(discount(T)) for T in remaining_times)
        )

        # For Tk <= t < Tk+1, the remaining floating-leg value is
        # N[A(Tk,t) - P(t,Tn)] in the single-curve OIS framework.
        floating_leg = self.notional * (floating_accrual_factor - np.asarray(discount(self.maturity)))

        if self.pay_fixed:
            return floating_leg - fixed_leg

        return fixed_leg - floating_leg

    def pv_at_reset(
        self,
        t: float,
        discount: Callable[[float], ArrayLike],
    ) -> np.ndarray:
        """Backward-compatible reset/payment-date valuation."""
        return self.pv_at_time(
            t=t,
            discount=discount,
            floating_accrual_factor=1.0,
        )
