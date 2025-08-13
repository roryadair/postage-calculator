import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
from decimal import Decimal, ROUND_HALF_UP

# USPS comprehensive rate table
usps_rates = {
    "letter": {
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
    },
    "flat": {
        "First-Class Mail": {
            "automation": {
                1.0: float(Decimal("1.230").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                2.0: float(Decimal("1.505").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                3.0: float(Decimal("1.775").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                4.0: float(Decimal("2.045").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                5.0: float(Decimal("2.325").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                6.0: float(Decimal("2.305").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            }
        },
        "Marketing Mail": {
            "automation": {
                1.0: float(Decimal("0.986").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                2.0: float(Decimal("0.986").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                3.0: float(Decimal("0.986").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                4.0: float(Decimal("0.986").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                5.0: float(Decimal("1.073").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                6.0: float(Decimal("1.119").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            }
        }
    }
}

# (rest of the code remains unchanged)

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
        # Treat digest like letter unless weight forces flat
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


def calculate_postage(weight_oz, shape, mail_class, mail_type, sortation_level=None):
    """Robust calculator that tolerates capitalization/aliases and avoids KeyErrors."""
    rounded_weight = round(weight_oz * 2) / 2

    shape_key = _normalize_shape(shape, weight_oz)
    mail_class_key = _normalize_mail_class(mail_class)
    mail_type_key = _normalize_mail_type(mail_type)

    # Auto-switch to flat for > 3.5 oz if user chose letter
    if shape_key == "letter" and weight_oz > 3.5:
        shape_key = "flat"
        sortation_level = None

    # Letters: need a sortation-level lookup
    if shape_key == "letter":
        rate = (
            usps_rates.get(shape_key, {})
                      .get(mail_class_key, {})
                      .get(mail_type_key, {})
                      .get(sortation_level)
        )
        if rate is None:
            return "Rate not found", shape_key.capitalize()
        return rate, shape_key.capitalize()

    # Flats: need a weight-based lookup
    weight_table = (
        usps_rates.get(shape_key, {})
                  .get(mail_class_key, {})
                  .get(mail_type_key)
    )
    if not isinstance(weight_table, dict) or not weight_table:
        return "Rate not found", shape_key.capitalize()

    # Choose the smallest listed weight >= rounded_weight; fallback to max
    eligible = sorted(w for w in weight_table.keys() if w >= rounded_weight)
    chosen_w = eligible[0] if eligible else max(weight_table.keys())
    rate = weight_table.get(chosen_w)

    if rate is None:
        return "Rate not found", shape_key.capitalize()
    return rate, shape_key.capitalize()

# Thin wrapper for compatibility with other files that call `calculate_usps_rate`
def calculate_usps_rate(weight_oz, shape, mail_class, mail_type, sortation_level=None):
    rate, _ = calculate_postage(weight_oz, shape, mail_class, mail_type, sortation_level)
    return rate


def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, value in data.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    return BytesIO(pdf_bytes)

st.set_page_config(page_title="Postage Calculator", layout="centered")
st.title("📬 USPS Postage Calculator")

st.header("Package Details")

weight = st.number_input("Weight (oz)", min_value=0.1, max_value=70.0, step=0.1)

# Automatically switch shape to "Flat" if weight > 3.5 oz
default_shape = "Flat" if weight > 3.5 else "Letter"
if weight > 3.5:
    st.info("Weight exceeds 3.5 oz — Shape automatically switched to 'Flat'.")
shape = st.selectbox("Shape (Digest = Letter ≤ 3.5 oz)", ["Letter", "Flat"], index=["Letter", "Flat"].index(default_shape))

quantity = st.number_input("Quantity", min_value=1, step=1)
mail_class = st.selectbox("Mail Class", ["First-Class Mail", "Marketing Mail"])
type_options = ["Automation"]
mail_type = st.selectbox("Type", type_options)

sortation_level = None
if shape == "Letter" and weight <= 3.5:
    sortation_level = st.selectbox("Sortation Level", ["5-Digit", "AADC", "Mixed AADC"])

st.header("ZIP Codes (Optional)")
origin_zip = st.text_input("Origin ZIP Code", max_chars=5)
dest_zip = st.text_input("Destination ZIP Code", max_chars=5)

export_format = st.selectbox("Export Format", ["None", "CSV", "PDF"])

if st.button("Calculate Postage"):
    st.subheader("Estimated Postage")
    rate, adjusted_shape = calculate_postage(weight, shape, mail_class, mail_type, sortation_level)

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
            "Total Cost": f"${total:.2f}"
        }

        if export_format == "CSV":
            df = pd.DataFrame([result_data])
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "postage_estimate.csv", "text/csv")

        elif export_format == "PDF":
            pdf = generate_pdf(result_data)
            st.download_button("Download PDF", pdf, "postage_estimate.pdf", "application/pdf")

    st.markdown(f"**Shape**: {adjusted_shape}\n\n**Mail Class**: {mail_class}\n\n**Type**: {mail_type}\n\n**Weight**: {weight} oz\n\n**Quantity**: {quantity}")
    if sortation_level:
        st.markdown(f"**Sortation Level**: {sortation_level}")
    if origin_zip and dest_zip:
        st.markdown(f"**From**: {origin_zip} → **To**: {dest_zip}")
        st.info("Zone-based pricing will be applied in a future version.")
    else:
        st.info("Flat-rate logic is used (no zones).")
