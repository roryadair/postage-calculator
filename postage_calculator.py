import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
from decimal import Decimal, ROUND_HALF_UP

# -----------------------------
# Load USPS Rates from Excel
# -----------------------------
RATE_FILE = "usps_rates.xlsx"
usps_rates = {"letter": {}, "flat": {}}

# Load Letter Rates
letter_df = pd.read_excel(RATE_FILE, sheet_name="USPS_Letter_Rates")
for _, row in letter_df.iterrows():
    mail_class = row["Mail Class"].strip()
    sort_level = row["Sortation Level"].strip()
    rate = float(row["Rate"])
    usps_rates["letter"].setdefault(mail_class, {}).setdefault("automation", {}).setdefault(sort_level, {})[3.5] = rate

# Load Flat Rates
flat_df = pd.read_excel(RATE_FILE, sheet_name="USPS_Flat_Rates")
for _, row in flat_df.iterrows():
    mail_class = row["Mail Class"].strip()
    weight = float(row["Weight (oz)"])
    rate = float(row["Rate"])
    usps_rates["flat"].setdefault(mail_class, {}).setdefault("automation", {})[weight] = rate

# Extrapolate flat rates up to 12oz
for mail_class in usps_rates["flat"]:
    rates = usps_rates["flat"][mail_class]["automation"]
    max_weight = max(rates.keys())
    max_rate = rates[max_weight]
    for oz in range(int(max_weight)+1, 13):
        estimated = Decimal(str(max_rate + 0.20 * (oz - max_weight))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rates[oz] = float(estimated)

# -----------------------------
# Postage Calculation Logic
# -----------------------------
def calculate_usps_rate(weight, shape, mail_class, sort_level):
    shape_key = shape.lower()
    mail_class = mail_class.strip()
    rounded_weight = round(weight * 2) / 2  # round to nearest 0.5

    try:
        if shape_key == "letter" and weight <= 3.5:
            return usps_rates["letter"][mail_class]["automation"][sort_level][3.5], "Letter"
        else:
            # Default to flat for anything over 3.5 oz
            weight_rates = usps_rates["flat"][mail_class]["automation"]
            closest = min((w for w in weight_rates if w >= rounded_weight), default=None)
            return weight_rates.get(closest, "Rate not found"), "Flat"
    except KeyError:
        return "Rate not found", shape.capitalize()

# -----------------------------
# PDF Export Function
# -----------------------------
def generate_pdf(data: dict) -> BytesIO:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, val in data.items():
        pdf.cell(200, 10, txt=f"{key}: {val}", ln=True)
    return BytesIO(pdf.output(dest="S").encode("latin-1"))

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="USPS Postage Calculator", layout="centered")
st.title("📬 USPS Postage Calculator")

st.header("Package Details")
weight = st.number_input("Weight (oz)", min_value=0.1, max_value=70.0, step=0.1)

# Auto-switch shape based on weight
default_shape = "Flat" if weight > 3.5 else "Letter"
if weight > 3.5:
    st.info("Weight exceeds 3.5 oz — Shape switched to 'Flat'")
shape = st.selectbox("Shape", ["Letter", "Flat"], index=["Letter", "Flat"].index(default_shape))

quantity = st.number_input("Quantity", min_value=1, step=1)
mail_class = st.selectbox("Mail Class", ["First-Class Mail", "Marketing Mail"])
sortation_level = None
if shape == "Letter" and weight <= 3.5:
    sortation_level = st.selectbox("Sortation Level", ["5-Digit", "AADC", "Mixed AADC"])

st.header("ZIP Codes (Optional)")
origin_zip = st.text_input("Origin ZIP", max_chars=5)
dest_zip = st.text_input("Destination ZIP", max_chars=5)

export_format = st.selectbox("Export Format", ["None", "CSV", "PDF"])

# -----------------------------
# Calculate Postage
# -----------------------------
if st.button("Calculate Postage"):
    st.subheader("Estimated Postage")
    rate, adjusted_shape = calculate_usps_rate(weight, shape, mail_class, sortation_level)

    if isinstance(rate, str):
        st.error(rate)
    else:
        total = rate * quantity
        st.success(f"Cost per Piece: ${rate:.2f}")
        st.success(f"Total Cost: ${total:.2f}")

        result_data = {
            "Shape": adjusted_shape,
            "Mail Class": mail_class,
            "Weight (oz)": weight,
            "Quantity": quantity,
            "Sortation Level": sortation_level or "N/A",
            "Origin ZIP": origin_zip or "N/A",
            "Destination ZIP": dest_zip or "N/A",
            "Cost per Piece": f"${rate:.2f}",
            "Total Cost": f"${total:.2f}",
        }

        # Export logic
        if export_format == "CSV":
            df = pd.DataFrame([result_data])
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "postage_estimate.csv", "text/csv")
        elif export_format == "PDF":
            pdf = generate_pdf(result_data)
            st.download_button("Download PDF", pdf, "postage_estimate.pdf", "application/pdf")

        st.markdown("\n".join([f"**{k}**: {v}" for k, v in result_data.items()]))

        if origin_zip and dest_zip:
            st.info("Zone-based pricing logic is not yet implemented.")
        else:
            st.info("Default flat-rate logic applied.")
