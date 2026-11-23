"""
Centralized INR Currency and Manufacturing Unit Formatting Utility.
Provides deterministic, standard Indian currency formatting (Rupees, Lakhs, Crores)
and manufacturing production unit formatting. Zero floating-point drift.
"""

from typing import Union

Number = Union[int, float]


def format_inr(amount: Number, precision: int = 2) -> str:
    """Formats a number as standard comma-separated INR currency string without leading symbols (e.g. ₹3,144,056,862.26)."""
    val = abs(float(amount or 0.0))
    if val < 1e-9:
        val = 0.0
    return f"₹{val:,.{precision}f}"


def format_crores(amount: Number, precision: int = 2) -> str:
    """
    Converts amount in INR to Crores (1 Crore = 10,000,000 INR) with absolute positive formatting.
    Example: 3,004,312,504.55 -> '₹300.43 Cr'
    """
    cr_val = abs(float(amount or 0.0)) / 10_000_000.0
    if cr_val < 1e-9:
        cr_val = 0.0
    return f"₹{cr_val:,.{precision}f} Cr"


def format_lakhs(amount: Number, precision: int = 2) -> str:
    """
    Converts amount in INR to Lakhs (1 Lakh = 100,000 INR) with absolute positive formatting.
    Example: 5,131,513.50 -> '₹51.32 Lakhs'
    """
    lakh_val = abs(float(amount or 0.0)) / 100_000.0
    if lakh_val < 1e-9:
        lakh_val = 0.0
    return f"₹{lakh_val:,.{precision}f} Lakhs"


def format_currency_auto(amount: Number, precision: int = 2) -> str:
    """
    Automatically formats currency into the most appropriate human-readable denomination:
    - >= ₹1 Crore (10,000,000): formatted in Crores (₹X.XX Cr)
    - >= ₹1 Lakh (100,000): formatted in Lakhs (₹X.XX Lakhs)
    - < ₹1 Lakh: formatted with comma-separated standard INR (₹XX,XXX.XX)
    """
    abs_amt = abs(float(amount or 0.0))
    if abs_amt >= 10_000_000.0:
        return format_crores(abs_amt, precision=precision)
    elif abs_amt >= 100_000.0:
        return format_lakhs(abs_amt, precision=precision)
    else:
        return format_inr(abs_amt, precision=precision)


def format_units(qty: Number, precision: int = 0) -> str:
    """Formats production quantities as comma-separated integers or floats."""
    val = abs(float(qty or 0.0))
    if precision == 0:
        return f"{round(val):,} units"
    return f"{val:,.{precision}f} units"


def format_pct(percentage: Number, precision: int = 2, show_plus: bool = False) -> str:
    """Formats percentage string with absolute value (no leading plus or hyphen)."""
    val = abs(float(percentage or 0.0))
    return f"{val:.{precision}f}%"
