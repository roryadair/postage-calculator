import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
from decimal import Decimal, ROUND_HALF_UP

# --- Load Rates from Excel File ---
uploaded_file = "All_Rate_Tables 08 13 2025.xlsx"
usps_rates = {"letter": {}, "flat": {}}
command_rates = {"letter": {}, "flat": {}}

# --- USPS Letter Rates ---
usps_letter_df = pd.read_excel(uploaded_file, sheet_name="USPS_Letter_Rates")
for _, row in usps_letter_df.iterrows():
    shape = "letter"
    mail_class = row["Mail Class"]
    mail_type = "automation"
    sort_level = row["Sortation Level"]
    rate = float(row["Rate"])

    usps_rates[shape].setdefault(mail_class, {}).setdefault(mail_type, {})[sort_level] = rate

# --- USPS Flat Rates ---
usps_flat_df = pd.read_excel(uploaded_file, sheet_name="USPS_Flat_Rates")
for _, row in usps_flat_df.iterrows():
    shape = "flat"
    mail_class = row["Mail Class"]
    mail_type = "automation"
    weight = float(row["Weight (oz)"])
    rate = float(row["Rate"])

    usps_rates[shape].setdefault(mail_class, {}).setdefault(mail_type, {})[weight] = rate

# --- Command Financial Digest Size (Letters) ---
cmd_digest_df = pd.read_excel(uploaded_file, sheet_name="Digest_Size_Rates")
for _, row in cmd_digest_df.iterrows():
    shape = "letter"
    mail_class = row["Mail Class"]
    mail_type = "automation"
    sort_level = row["Sortation Level"]
    rate = float(row["Rate"])

    command_rates[shape].setdefault(mail_class, {}).setdefault(mail_type, {})[sort_level] = rate

# --- Command Financial Full Size (Flats) ---
cmd_full_df = pd.read_excel(uploaded_file, sheet_name="Full_Size_Rates")
for _, row in cmd_full_df.iterrows():
    shape = "flat"
    mail_class = row["Mail Class"]
    mail_type = "automation"
    weight = float(row["Weight (oz)"])
    rate = float(row["Rate"])

    command_rates[shape].setdefault(mail_class, {}).setdefault(mail_type, {})[weight] = rate


def calculate_postage(weight_oz, shape, mail_class, mail_type, sortation_level, rate_table):
    mail_type = mail_type.lower()
    mail_class = mail_class.strip()
    rounded_weight = round(weight_oz * 2) / 2

    if shape.lower() == "letter" and weight_oz > 3.5:
        shape = "flat"
        sortation_level = None

    shape = shape.lower()

    try:
        if shape == "letter":
            rate = rate_table[shape][mail_class][mail_type].get(sortation_level, "N/A")
        else:
            available_weights = rate_table[shape][mail_class][mail_type]
            closest = min((w for w in available_weights if w >= rounded_weight), default=None)
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


# --- UI Begins ---
st.set_page_config(page_title="Postage Calculator", layout="centered")
st.title("📬 USPS & Command Financial Postage Calculator")

# Sidebar toggle for rate source
st.sidebar.title("Rate Source")
rate_provider = st.sidebar.radio("Choose rate table:", ["USPS", "Command Financial"])
rate_table = usps_rates if rate_provider == "USPS" else command_rates

# User inputs
st.header("Package Details")
weight = st.number_input("Weight (oz)", min_value=0.1, max_value=70.0, step=0.1)

# Shape determination with automatic override
default_shape = "Flat" if weight > 3.5 else "Letter"
if weight > 3.5:
    st.info("Weight exceeds 3.5 oz — Shape automatically switched to 'Flat'.")
shape = st.selectbox("Shape", ["Letter", "Flat"], index=["Letter", "Flat"].index(default_shape))

quantity = st.number_input("Quantity", min_value=1, step=1)
mail_class = st.selectbox("Mail Class", ["First-Class Mail", "Marketing Mail"])
mail_type = st.selectbox("Type", ["Automation"])

# Sortation Level only appears for letters 3.5 oz or less
sortation_level = None
if shape == "Letter" and weight <= 3.5:
    sortation_level = st.selectbox("Sortation Level", ["5-Digit", "AADC", "Mixed AADC"])

# Optional ZIP code inputs
st.header("ZIP Codes (Optional)")
origin_zip = st.text_input("Origin ZIP Code", max_chars=5)
dest_zip = st.text_input("Destination ZIP Code", max_chars=5)

# Export format selector
export_format = st.selectbox("Export Format", ["None", "CSV", "PDF"])

# Calculate Postage button
if st.button("Calculate Postage"):
    st.subheader("Estimated Postage")
    rate, adjusted_shape = calculate_postage(weight, shape, mail_class, mail_type, sortation_level, rate_table)

    if isinstance(rate, str):
        st.error(rate)
    else:
        total = rate * quantity
        st.success(f"Estimated Cost per Piece: ${rate:.2f}")
        st.success(f"Total Cost for {quantity} Pieces: ${total:.2f}")

        result_data = {
            "Rate Source": rate_provider,
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

        # Display summary
        st.markdown("\n".join([f"**{k}**: {v}" for k, v in result_data.items()]))

        if origin_zip and dest_zip:
            st.info("Zone-based pricing will be applied in a future version.")
        else:
            st.info("Flat-rate logic is used (no zones).")
