import streamlit as st

# USPS rate table (from Excel file)
usps_rates = {
    "letter": {
        "automation": {
            "5-Digit": 0.593,
            "AADC": 0.641,
            "Mixed AADC": 0.672
        },
        "non-machinable": {
            "5-Digit": 0.66,
            "AADC": 0.70,
            "Mixed AADC": 0.75
        }
    },
    "flat": {
        "automation": {
            1.0: 1.23,
            2.0: 1.505,
            3.0: 1.775,
            4.0: 2.045,
            5.0: 2.325,
            6.0: 2.305
        }
    },
    "parcel": {
        "retail": {
            1.0: 4.75,
            2.0: 4.95,
            3.0: 5.15,
            4.0: 5.35
        }
    }
}

def calculate_postage(weight_oz, shape, mail_type, sortation_level=None):
    shape = shape.lower()
    mail_type = mail_type.lower()
    rounded_weight = round(weight_oz * 2) / 2

    try:
        if shape == "letter":
            rate = usps_rates[shape][mail_type].get(sortation_level, "N/A")
        else:
            available_weights = usps_rates[shape][mail_type]
            closest = min(available_weights.keys(), key=lambda w: w if w >= rounded_weight else float('inf'))
            rate = available_weights.get(closest, "N/A")
        return rate
    except KeyError:
        return "Rate not found"

st.set_page_config(page_title="Postage Calculator", layout="centered")
st.title("📬 USPS Postage Calculator")

st.header("Package Details")

weight = st.number_input("Weight (oz)", min_value=0.1, max_value=70.0, step=0.1)
shape = st.selectbox("Shape", ["Letter", "Flat", "Parcel"])
type_options = {
    "Letter": ["Automation", "Non-machinable"],
    "Flat": ["Automation"],
    "Parcel": ["Retail"]
}
mail_type = st.selectbox("Type", type_options.get(shape, ["Retail"]))

sortation_options = ["5-Digit", "AADC", "Mixed AADC"] if shape == "Letter" else []
sortation_level = None
if sortation_options:
    sortation_level = st.selectbox("Sortation Level", sortation_options)

st.header("ZIP Codes (Optional)")
origin_zip = st.text_input("Origin ZIP Code", max_chars=5)
dest_zip = st.text_input("Destination ZIP Code", max_chars=5)

if st.button("Calculate Postage"):
    st.subheader("Estimated Postage")
    rate = calculate_postage(weight, shape, mail_type, sortation_level)

    if isinstance(rate, str):
        st.error(rate)
    else:
        st.success(f"Estimated Cost: ${rate:.2f}")

    st.markdown(f"**Shape**: {shape}\n\n**Type**: {mail_type}\n\n**Weight**: {weight} oz")
    if sortation_level:
        st.markdown(f"**Sortation Level**: {sortation_level}")
    if origin_zip and dest_zip:
        st.markdown(f"**From**: {origin_zip} → **To**: {dest_zip}")
        st.info("Zone-based pricing will be applied in a future version.")
    else:
        st.info("Flat-rate logic is used (no zones).")
