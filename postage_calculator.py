import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
from decimal import Decimal, ROUND_HALF_UP

# USPS comprehensive rate table (updated for proper 2-decimal rounding)
usps_rates = {
    "letter": {
        "First-Class Mail": {
            "automation": {
                "5-Digit": float(Decimal("0.593").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "AADC": float(Decimal("0.641").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "Mixed AADC": float(Decimal("0.672").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            }
        },
        "Marketing Mail": {
            "automation": {
                "5-Digit": float(Decimal("0.372").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "AADC": float(Decimal("0.407").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "Mixed AADC": float(Decimal("0.433").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            }
        }
    },
    "flat": {
        "First-Class Mail": {
            "automation": {
                1.0: float(Decimal("1.23").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                2.0: float(Decimal("1.51").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                3.0: float(Decimal("1.78").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                4.0: float(Decimal("2.05").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                5.0: float(Decimal("2.33").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                6.0: float(Decimal("2.31").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            }
        },
        "Marketing Mail": {
            "automation": {
                1.0: float(Decimal("0.99").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                2.0: float(Decimal("0.99").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                3.0: float(Decimal("0.99").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                4.0: float(Decimal("0.99").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                5.0: float(Decimal("1.07").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                6.0: float(Decimal("1.12").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            }
        }
    }
}

# Placeholder Command Financial rates (to be loaded later)
command_rates = {
    "letter": {},
    "flat": {}
}

# --- Normalization helpers & robust lookup ---
MAIL_CLASS_ALIASES = {
    "first-class mail": "First-Class Mail",
    "first class mail": "First-Class Mail",
    "first class": "First-Class Mail",
    "fcm": "First-Class Mail",
    "marketing mail": "Marketing Mail",
    "std prst": "Marketing Mail",
    "standard presort": "Marketing Mail"
}

MAIL_TYPE_ALIASES = {
    "automation": "automation",
    "auto": "automation",
    "non-machinable": "non-machinable",
    "non machinable": "non-machinable",
}

def _normalize_shape(shape: str, weight_oz: float) -> str:
    s = (shape or "").strip().lower()
    if s in ("digest",):
        s = "letter" if weight_oz <= 3.5 else "flat"
    if s not in ("letter", "flat"):
        s = "flat" if weight_oz > 3.5 else "letter"
    return s

def _normalize_mail_class(mail_class: str) -> str:
    mc = (mail_class or "").strip().lower()
    return MAIL_CLASS_ALIASES.get(mc, mail_class)

def _normalize_mail_type(mail_type: str) -> str:
    mt = (mail_type or "").strip().lower()
    return MAIL_TYPE_ALIASES.get(mt, mt)

def calculate_postage(weight_oz, shape, mail_class, mail_type, sortation_level=None, rates_table=None):
    rates = rates_table or usps_rates
    rounded_weight = round(weight_oz * 2) / 2

    shape_key = _normalize_shape(shape, weight_oz)
    mail_class_key = _normalize_mail_class(mail_class)
    mail_type_key = _normalize_mail_type(mail_type)

    if shape_key == "letter" and weight_oz > 3.5:
        shape_key = "flat"
        sortation_level = None

    if shape_key == "letter":
        rate = (
            rates.get(shape_key, {})
                 .get(mail_class_key, {})
                 .get(mail_type_key, {})
                 .get(sortation_level)
        )
        if rate is None:
            return "Rate not found", shape_key.capitalize()
        return rate, shape_key.capitalize()

    weight_table = (
        rates.get(shape_key, {})
             .get(mail_class_key, {})
             .get(mail_type_key)
    )
    if not isinstance(weight_table, dict) or not weight_table:
        return "Rate not found", shape_key.capitalize()

    eligible = sorted(w for w in weight_table.keys() if w >= rounded_weight)
    chosen_w = eligible[0] if eligible else max(weight_table.keys())
    rate = weight_table.get(chosen_w)

    if rate is None:
        return "Rate not found", shape_key.capitalize()
    return rate, shape_key.capitalize()

def calculate_usps_rate(weight_oz, shape, mail_class, mail_type, sortation_level=None, rates_table=None):
    rate, _ = calculate_postage(weight_oz, shape, mail_class, mail_type, sortation_level, rates_table or usps_rates)
    return rate

def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, value in data.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    return BytesIO(pdf_bytes)

# Toggle between USPS and Command Financial
st.sidebar.title("Rate Source")
rate_provider = st.sidebar.radio("Choose rate table:", ["USPS", "Command Financial"])
rate_table = usps_rates if rate_provider == "USPS" else command_rates

# Example call:
# rate, shape = calculate_postage(weight, shape, mail_class, mail_type, sortation_level, rate_table)

# The rest of the Streamlit UI continues as usual...
