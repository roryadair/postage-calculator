import streamlit as st

st.set_page_config(page_title="Postage Calculator", layout="centered")
st.title("📬 USPS Postage Calculator")

# Input fields
st.header("Package Details")

weight = st.number_input("Weight (oz)", min_value=0.1, max_value=70.0, step=0.1)
shape = st.selectbox("Shape", ["Letter", "Flat", "Parcel"])
type_options = {
    "Letter": ["Automation", "Non-machinable"],
    "Flat": ["Automation"],
    "Parcel": ["Retail"]
}
mail_type = st.selectbox("Type", type_options.get(shape, ["Retail"]))

st.header("ZIP Codes (Optional)")
origin_zip = st.text_input("Origin ZIP Code", max_chars=5)
dest_zip = st.text_input("Destination ZIP Code", max_chars=5)

# Placeholder calculation logic
if st.button("Calculate Postage"):
    st.subheader("Estimated Postage")
    st.write("This is a placeholder result. Actual rates will be loaded from USPS rate tables.")
    st.write(f"**Shape**: {shape}")
    st.write(f"**Type**: {mail_type}")
    st.write(f"**Weight**: {weight} oz")
    if origin_zip and dest_zip:
        st.write(f"**From**: {origin_zip}  →  **To**: {dest_zip}")
        st.write("Zone-based pricing will be applied in the future.")
    else:
        st.write("Flat-rate logic will apply for now.")
