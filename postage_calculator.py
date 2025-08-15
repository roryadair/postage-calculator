import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Dict

# =========================
# Configuration / Toggles
# =========================
# If you want a smooth +$0.280/oz progression for First-Class 6 oz (instead of 2.305),
# set this to True. By default we keep your exact seed value.
CORRECT_FC_6OZ = False

MAX_FLAT_OZ = 12  # extrapolate and support flats 1..12 oz

# =========================
# Helpers
# =========================
def to_cents(x: Decimal) -> float:
    """Round to 2 decimals (banker's rounding turned OFF)."""
    return float(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def extend_flat_rates_to_12oz(seed: Dict[float, float], step: Decimal) -> Dict[float, float]:
    """
    From a {1.0..6.0} seed dict, extend forward with a constant step to 12.0 ounces.
    Returns a NEW dict with keys 1.0..12.0 (floats) and values rounded to cents.
    """
    out_dec = {Decimal(str(k)): Decimal(str(v)) for k, v in seed.items()}
    # The seed keys are continuous up to 6.0 by design
    for oz in range(7, MAX_FLAT_OZ + 1):
        prev = out_dec[Decimal(oz - 1)]
        out_dec[Decimal(oz)] = prev + step
    return {float(k): to_cents(v) for k, v in out_dec.items()}

def rounded_ounces(weight_oz: float) -> int:
    """USPS bills flats/packages by rounding UP to the next whole ounce."""
    return math.ceil(weight_oz)

# =========================
# Seed Tables (your exact values)
# =========================
# Letters: single price at 3.5 oz equivalent by sortation level
LETTER_RATES = {
    "First-Class Mail": {
        "automation": {
            "5-Digit": 0.593,
            "AADC": 0.641,
            "Mixed AADC": 0.672
        }
    },
    "Marketing Mail": {
        "automation": {
            "5-Digit": 0.372,
            "AADC": 0.407,
            "Mixed AADC": 0.433
        }
    }
}

# Flats seed 1..6 oz (your original table)
FC_FLAT_SEED_1_TO_6 = {
    1.0: 1.230,
    2.0: 1.505,
    3.0: 1.775,
    4.0: 2.045,
    5.0: 2.325,
    # Keep your 6 oz value unless smoothing is turned on
    6.0: (2.325 + 0.280) if CORRECT_FC_6OZ else 2.305
}

MM_FLAT_SEED_1_TO_6 = {
    1.0: 0.986,
    2.0: 0.986,
    3.0: 0.986,
    4.0: 0.986,
    5.0: 1.073,
    6.0: 1.119
}

# Extrapolation steps derived from your table
FC_STEP = Decimal("0.280")  # First-Class flats step per ounce
MM_STEP = Decimal("0.046")  # Marketing flats step per ounce

# Build extended flat tables (1..12 oz)
FC_FLAT_EXTENDED = extend_flat_rates_to_12oz(FC_FLAT_SEED_1_TO_6, FC_STEP)
MM_FLAT_EXTENDED = extend_flat_rates_to_12oz(MM_FLAT_SEED_1_TO_6, MM_STEP)

# =========================
# Unified Rates Structure
# =========================
usps_rates = {
    "letter": LETTER_RATES,
    "flat": {
        "First-Class Mail": {"automation": FC_FLAT_EXTENDED},
        "Marketing Mail": {"automation": MM_FLAT_EXTENDED}
    }
}

# =========================
# Core Calculation
# =========================
def calculate_postage(weight_oz, shape, mail_class, mail_type, sortation_level=None):
    """
    Returns (rate, adjusted_shape) or ("Rate not found", adjusted_shape).
    - Letters: single rate from sortation level (5-Digit/AADC/Mixed AADC)
    - Flats: extrapolated per-ounce table 1..12 oz, rounded UP to whole oz
    """
    mail_type = mail_type.lower().strip()     # "automation"
    mail_class = mail_class.strip()           # "First-Class Mail" | "Marketing Mail"
    shape = shape.lower().strip()             # "letter" | "flat"

    # Auto-switch Letter → Flat when weight > 3.5 oz
    if shape == "letter" and weight_oz > 3.5:
        shape = "flat"
        sortation_level = None

    try:
        if shape == "letter":
            rate = usps_rates["letter"][mail_class][mail_type].get(sortation_level, "N/A")
            return rate, shape.capitalize()

        # shape == "flat"
        available = usps_rates["flat"][mail_class][mail_type]  # dict of {1.0:rate ... 12.0:rate}
        rounded_whole = rounded_ounces(weight_oz)
        if rounded_whole < 1:
            rounded_whole = 1
        if rounded_whole > MAX_FLAT_OZ:
            return f"Rate not found (supported up to {MAX_FLAT_OZ} oz)", shape.capitalize()

        key = float(rounded_whole)
        rate = available.get(key, "N/A")
        return rate, shape.capitalize()
    except KeyError:
        return "Rate not found", shape.capitalize()

# =========================
# PDF Export
# =========================
def generate_pdf(data: Dict[str, str]) -> BytesIO:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, value in data.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    return BytesIO(pdf_bytes)

# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Postage Calculator", layout="centered")
st.title("📬 USPS Postage Calculator")

st.caption(
    "Hardcoded from your 1–6 oz table with deterministic extrapolation to 12 oz. "
    "Flats are billed by rounding up to the next whole ounce."
)

st.header("Package Details")
weight = st.number_input("Weight (oz)", min_value=0.1, max_value=70.0, step=0.1)

# Automatically switch shape to Flat if weight > 3.5 oz
default_shape = "Flat" if weight > 3.5 else "Letter"
if weight > 3.5:
    st.info("Weight exceeds 3.5 oz — shape switched to 'Flat'.")
shape = st.selectbox(
    "Shape (Digest = Letter ≤ 3.5 oz)",
    ["Letter", "Flat"],
    index=["Letter", "Flat"].index(default_shape),
)

quantity = st.number_input("Quantity", min_value=1, step=1)
mail_class = st.selectbox("Mail Class", ["First-Class Mail", "Marketing Mail"])
mail_type = st.selectbox("Type", ["Automation"])

sortation_level = None
if shape == "Letter" and weight <= 3.5:
    sortation_level = st.selectbox("Sortation Level", ["5-Digit", "AADC", "Mixed AADC"])

st.header("ZIP Codes (Optional)")
origin_zip = st.text_input("Origin ZIP Code", max_chars=5)
dest_zip = st.text_input("Destination ZIP Code", max_chars=5)

export_format = st.selectbox("Export Format", ["None", "CSV", "PDF"])

if st.button("Calculate Postage"):
    st.subheader("Estimated Postage")

    rate, adjusted_shape = calculate_postage(
        weight, shape, mail_class, mail_type, sortation_level
    )

    if isinstance(rate, str):
        st.error(rate)
    else:
        total = rate * quantity
        st.success(f"Estimated Cost per Piece: ${rate:.2f}")
        st.success(f"Total Cost for {quantity} Pieces: ${total:.2f}")

        result_data = {
            "Shape": adjusted_shape,
            "Mail Class": mail_class,
            "Type": mail_type,
            "Weight (oz)": weight,
            "Quantity": quantity,
            "Sortation Level": sortation_level or "N/A",
            "Origin ZIP": origin_zip or "N/A",
            "Destination ZIP": dest_zip or "N/A",
            "Cost per Piece": f"${rate:.2f}",
            "Total Cost": f"${total:.2f}",
            "Rounded Ounces (Flats)": rounded_ounces(weight) if adjusted_shape == "Flat" else "N/A",
            "FC 6 oz smoothing": "ON" if CORRECT_FC_6OZ else "OFF",
        }

        if export_format == "CSV":
            df = pd.DataFrame([result_data])
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "postage_estimate.csv", "text/csv")

        elif export_format == "PDF":
            pdf = generate_pdf(result_data)
            st.download_button("Download PDF", pdf, "postage_estimate.pdf", "application/pdf")

        # Summary block
        st.markdown("\n".join([f"**{k}**: {v}" for k, v in result_data.items()]))

        # Guidance note on zones
        if origin_zip and dest_zip:
            st.info("Zone-based pricing will be applied in a future version.")
        else:
            st.info("Flat-rate logic is used (no zones).")

# Optional: show the extrapolated tables for quick visual verification
with st.expander("Show extrapolated flat tables (1–12 oz)"):
    fc_rows = [{"Ounces": int(oz), "Type": "First-Class Flats (Automation 3-Digit)", "Rate ($)": rate}
               for oz, rate in sorted(FC_FLAT_EXTENDED.items(), key=lambda x: x[0])]
    mm_rows = [{"Ounces": int(oz), "Type": "Marketing Flats (Automation)", "Rate ($)": rate}
               for oz, rate in sorted(MM_FLAT_EXTENDED.items(), key=lambda x: x[0])]
    table_df = pd.DataFrame(fc_rows + mm_rows)
    st.dataframe(table_df, use_container_width=True)
