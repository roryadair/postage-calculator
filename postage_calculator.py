
import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
from decimal import Decimal, ROUND_HALF_UP

USPS_EXCEL_PATH = "/mnt/data/usps_rates.xlsx"

# ---------- Helpers to load ONLY the two sheets ----------
def _normalize_mail_class(category: str) -> str:
    cat = str(category)
    if "First-Class Mail" in cat:
        return "First-Class Mail"
    if "Marketing Mail" in cat:
        return "Marketing Mail"
    # fallback
    return cat.strip()

def load_usps_rates(file_path: str):
    """Load USPS rates from ONLY:
        - 'USPS_Letter_Rates' (columns: Category, 5-Digit, AADC, Mixed AADC)
        - 'USPS_Flat_Rates'   (columns: Category, 1oz, 2oz, 3oz, ...)
    Returns a nested dict: usps_rates[shape][mail_class][mail_type][...]
    """
    usps_rates = {"letter": {}, "flat": {}}

    # ----- Letters (assume up to 3.5 oz single-piece automation pricing by sort level) -----
    letter_df = pd.read_excel(file_path, sheet_name="USPS_Letter_Rates")
    expected_letter_cols = {"Category", "5-Digit", "AADC", "Mixed AADC"}
    missing_letter_cols = expected_letter_cols - set(letter_df.columns)
    if missing_letter_cols:
        raise ValueError(f"USPS_Letter_Rates is missing expected columns: {missing_letter_cols}")

    for _, row in letter_df.iterrows():
        mail_class = _normalize_mail_class(row["Category"])
        mail_type = "automation"
        sort_cols = ["5-Digit", "AADC", "Mixed AADC"]
        for sort_col in sort_cols:
            rate = row.get(sort_col)
            if pd.notna(rate):
                usps_rates["letter"].setdefault(mail_class, {}).setdefault(mail_type, {}).setdefault(sort_col, {})[3.5] = float(rate)

    # ----- Flats (columns like 1oz, 2oz, ... N oz) -----
    flat_df = pd.read_excel(file_path, sheet_name="USPS_Flat_Rates")
    # Identify weight columns like '1oz', '2oz', etc.
    weight_cols = [c for c in flat_df.columns if str(c).lower().endswith("oz")]
    if not weight_cols:
        raise ValueError("USPS_Flat_Rates has no weight columns ending with 'oz' (e.g., '1oz', '2oz').")

    for _, row in flat_df.iterrows():
        mail_class = _normalize_mail_class(row["Category"])
        mail_type = "automation"
        for wcol in weight_cols:
            try:
                weight_oz = float(str(wcol).lower().replace("oz", "").strip())
            except ValueError:
                continue
            rate = row.get(wcol)
            if pd.notna(rate):
                usps_rates["flat"].setdefault(mail_class, {}).setdefault(mail_type, {})[weight_oz] = float(rate)

    # Extrapolate flat weights up to 12 oz by a gentle increment if needed
    for mail_class, by_type in list(usps_rates["flat"].items()):
        for mail_type, weight_rates in list(by_type.items()):
            if not weight_rates:
                continue
            max_weight = max(weight_rates.keys())
            max_rate = weight_rates[max_weight]
            # If weights end before 12 oz, extend with small increments (e.g., $0.20 per oz)
            if max_weight < 12:
                for oz in range(int(max_weight) + 1, 13):
                    est_rate = Decimal(str(max_rate + 0.20 * (oz - max_weight))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    weight_rates[float(oz)] = float(est_rate)

    return usps_rates

def calculate_postage(weight_oz, shape, mail_class, mail_type, sortation_level, rate_table):
    # normalize
    mail_type = mail_type.lower().strip()
    mail_class = mail_class.strip()
    shape = shape.lower().strip()

    # Round to nearest 0.5 oz for flat lookups
    rounded_weight = round(weight_oz * 2) / 2

    # If letters exceed 3.5 oz, switch to flats
    if shape == "letter" and weight_oz > 3.5:
        shape = "flat"
        sortation_level = None

    try:
        if shape == "letter":
            # one rate up to 3.5 oz, by sortation level
            rate = rate_table["letter"][mail_class][mail_type][sortation_level][3.5]
        else:
            available_weights = rate_table["flat"][mail_class][mail_type]
            # choose the nearest available weight at or ABOVE the rounded weight
            candidates = [w for w in available_weights.keys() if w >= rounded_weight]
            closest = min(candidates) if candidates else max(available_weights.keys())
            rate = available_weights.get(closest, "N/A")
        return rate, shape.capitalize()
    except KeyError:
        return "Rate not found", shape.capitalize()

def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, value in data.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    return BytesIO(pdf_bytes)

# ---------- UI ----------
st.set_page_config(page_title="Postage Calculator", layout="centered")
st.title("📬 USPS Postage Calculator (Letters & Flats Only)")

# Load rates from ONLY the two sheets
try:
    usps_rates = load_usps_rates(USPS_EXCEL_PATH)
    st.success("USPS rates loaded from 'USPS_Letter_Rates' and 'USPS_Flat_Rates'.")
except Exception as e:
    st.error(f"Problem loading USPS rates: {e}")
    st.stop()

# Inputs
st.header("Package Details")
weight = st.number_input("Weight (oz)", min_value=0.1, max_value=70.0, step=0.1)

default_shape = "Flat" if weight > 3.5 else "Letter"
if weight > 3.5:
    st.info("Weight exceeds 3.5 oz — shape switched to 'Flat'.")
shape = st.selectbox("Shape", ["Letter", "Flat"], index=["Letter", "Flat"].index(default_shape))

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
    rate, adjusted_shape = calculate_postage(weight, shape, mail_class, mail_type, sortation_level, usps_rates)

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

        st.markdown("\n".join([f"**{k}**: {v}" for k, v in result_data.items()]))

        if origin_zip and dest_zip:
            st.info("Zone-based pricing will be applied in a future version.")
        else:
            st.info("Flat-rate logic is used (no zones).")
