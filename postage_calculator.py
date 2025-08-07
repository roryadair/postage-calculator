import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
from decimal import Decimal, ROUND_HALF_UP

# Load Excel rate tables
rate_file_path = "All_Rate_Tables 08 06 2025.xlsx"
full_df = pd.read_excel(rate_file_path, sheet_name="Full_Size_Rates")
digest_df = pd.read_excel(rate_file_path, sheet_name="Digest_Size_Rates")
letters_df = pd.read_excel(rate_file_path, sheet_name="Letters_LTE_3_5oz")
flats_df = pd.read_excel(rate_file_path, sheet_name="Flats_GT_QuarterInch")

letters_df.columns = ["Category", "5-Digit", "AADC", "Mixed AADC"]
flats_df.columns = ["Ounces", "First-Class Mail", "Marketing Mail"]
flats_df["Ounces"] = flats_df["Ounces"].str.replace("oz", "").astype(float)

# USPS automation rates for fallback or default
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
                1.0: 1.23, 2.0: 1.505, 3.0: 1.775, 4.0: 2.045, 5.0: 2.325, 6.0: 2.305
            }
        },
        "Marketing Mail": {
            "automation": {
                1.0: 0.986, 2.0: 0.986, 3.0: 0.986, 4.0: 0.986, 5.0: 1.073, 6.0: 1.119
            }
        }
    }
}

def calculate_command_rate(weight_oz, mail_class, size):
    df = digest_df if size == "Digest" else full_df
    df_sorted = df.sort_values("Weight (oz)")
    for i, row in df_sorted.iterrows():
        if weight_oz <= row["Weight (oz)"]:
            return row[mail_class]
    return df_sorted.iloc[-1][mail_class]  # default to last value if over max

def calculate_usps_rate(weight_oz, shape, mail_class, mail_type, sortation_level):
    rounded_weight = round(weight_oz * 2) / 2
    if shape == "letter" and weight_oz > 3.5:
        shape = "flat"
        sortation_level = None
    if shape == "letter":
        return usps_rates[shape][mail_class][mail_type].get(sortation_level, "N/A")
    else:
        available_weights = usps_rates[shape][mail_class][mail_type]
        closest = min((w for w in available_weights if w >= rounded_weight), default=None)
        return available_weights.get(closest, "N/A")

def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, value in data.items():
        pdf.cell(200, 10, txt=f"{key}: {value}", ln=True)
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    return BytesIO(pdf_bytes)

# Streamlit UI
st.set_page_config(page_title="Postage Calculator", layout="centered")
st.title("📬 USPS Postage Calculator")

st.header("Package Details")

weight = st.number_input("Weight (oz)", min_value=0.1, max_value=70.0, step=0.1)
shape = "Flat" if weight > 3.5 else "Letter"
if weight > 3.5:
    st.info("Weight exceeds 3.5 oz — Shape automatically switched to 'Flat'.")

quantity = st.number_input("Quantity", min_value=1, step=1)
mail_class = st.selectbox("Mail Class", [
    "First-Class Mail",
    "First-Class Mail Presort",
    "Standard Presort",
    "Marketing Mail"
])

# Automatically select rate source if applicable
if mail_class in ["First-Class Mail Presort", "Standard Presort"]:
    default_rate_source = "Command Financial (Full)"
else:
    default_rate_source = "USPS Automation"

rate_source = st.selectbox(
    "Rate Source",
    ["USPS Automation", "Command Financial (Full)", "Command Financial (Digest)"],
    index=["USPS Automation", "Command Financial (Full)", "Command Financial (Digest)"].index(default_rate_source)
)

sortation_level = None
if rate_source == "USPS Automation" and shape == "Letter" and weight <= 3.5:
    sortation_level = st.selectbox("Sortation Level", ["5-Digit", "AADC", "Mixed AADC"])

st.header("ZIP Codes (Optional)")
origin_zip = st.text_input("Origin ZIP Code", max_chars=5)
dest_zip = st.text_input("Destination ZIP Code", max_chars=5)
export_format = st.selectbox("Export Format", ["None", "CSV", "PDF"])

if st.button("Calculate Postage"):
    if "Command Financial" in rate_source:
        size = "Digest" if "Digest" in rate_source else "Full"
        rate = calculate_command_rate(weight, mail_class, size)
    else:
        shape_key = shape.lower()
        rate = calculate_usps_rate(weight, shape_key, mail_class, "automation", sortation_level)

    if isinstance(rate, str):
        st.error(rate)
    else:
        total = rate * quantity
        st.success(f"Estimated Cost per Piece: ${rate:.2f}")
        st.success(f"Total Cost for {quantity} Pieces: ${total:.2f}")

        result_data = {
            "Rate Source": rate_source,
            "Shape": shape,
            "Mail Class": mail_class,
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

# Reference Tables
with st.expander("📄 View Rate Tables"):
    st.subheader("Full Size Rates")
    st.dataframe(full_df)
    st.subheader("Digest Size Rates")
    st.dataframe(digest_df)
    st.subheader("USPS Letter Rates (<= 3.5oz)")
    st.dataframe(letters_df)
    st.subheader("USPS Flat Rates (1–6 oz)")
    st.dataframe(flats_df)

# Deployment Note
st.markdown("""
**ℹ️ Deployment Tip:** When running this in a hosted Streamlit environment (e.g. Streamlit Cloud), make sure to:
- Upload `All_Rate_Tables 08 06 2025.xlsx` to the same directory as this script.
- OR use `st.file_uploader()` if you want to support dynamic uploads.
""")
