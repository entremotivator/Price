import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO
from fpdf import FPDF
import base64

st.set_page_config(page_title="💼 Pricing & Services", layout="wide")

# --------------------------
# Constants
# --------------------------
SHEET_ID = "1WeDpcSNnfCrtx4F3bBC9osigPkzy3LXybRO6jpN7BXE"
VISIBLE_COLUMNS = ["Service Category", "Item", "Price (USD)", "Turnaround Time", "Notes"]

# --------------------------
# Sidebar Auth
# --------------------------
st.sidebar.header("🔐 Upload Google JSON Auth")
json_file = st.sidebar.file_uploader("Upload your Google Service Account .json", type="json")

def get_sheet_data(sheet_id, worksheet_index=0):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(eval(json_file.read()), scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(worksheet_index)
    return worksheet, pd.DataFrame(worksheet.get_all_records())

# --------------------------
# PDF Export Utility
# --------------------------
def export_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt="Pricing & Services", ln=True, align='C')
    for idx, row in df.iterrows():
        text = f"{row['Service Category']} | {row['Item']} | ${row['Price (USD)']} | {row['Turnaround Time']} | {row['Notes']}"
        pdf.cell(200, 8, txt=text, ln=True)
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    return pdf_buffer.getvalue()

# --------------------------
# App Logic
# --------------------------
if json_file:
    try:
        ws, df = get_sheet_data(SHEET_ID)
        df.columns = df.columns.str.strip()
        df = df[VISIBLE_COLUMNS]

        # --------------------------
        # Header and KPIs
        # --------------------------
        st.title("💼 Pricing & Services Dashboard")

        col1, col2, col3 = st.columns(3)
        col1.metric("🧾 Total Services", len(df))
        col2.metric("💲 Avg. Price (USD)", f"${df['Price (USD)'].mean():.2f}")
        col3.metric("🗂️ Categories", df['Service Category'].nunique())

        st.markdown("---")

        # --------------------------
        # Search & Filter
        # --------------------------
        st.subheader("🔍 Filter Services")
        category_filter = st.selectbox("Filter by Category", ["All"] + sorted(df["Service Category"].unique()))
        if category_filter != "All":
            df = df[df["Service Category"] == category_filter]

        search_term = st.text_input("Search Item or Notes")
        if search_term:
            df = df[df.apply(lambda row: search_term.lower() in str(row).lower(), axis=1)]

        st.dataframe(df, use_container_width=True)

        # --------------------------
        # Download Options
        # --------------------------
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⬇️ Download CSV", df.to_csv(index=False), "services.csv", "text/csv")
        with col2:
            pdf_data = export_pdf(df)
            st.download_button("🖨️ Export PDF", pdf_data, "services.pdf", "application/pdf")

        st.markdown("---")

        # --------------------------
        # Add New Service
        # --------------------------
        with st.expander("➕ Add New Service", expanded=False):
            with st.form("add_service_form"):
                new_cat = st.text_input("Service Category")
                new_item = st.text_input("Item")
                new_price = st.number_input("Price (USD)", min_value=0.0)
                new_turn = st.text_input("Turnaround Time")
                new_notes = st.text_area("Notes")
                add_submit = st.form_submit_button("✅ Add Service")
                if add_submit:
                    ws.append_row([new_cat, new_item, new_price, new_turn, new_notes])
                    st.success("Service added. Refresh the app.")

        # --------------------------
        # Edit Service
        # --------------------------
        with st.expander("✏️ Edit Existing Service"):
            row_num = st.number_input("Enter Row # to Edit (Starts from 2)", min_value=2, max_value=len(df)+1)
            selected_row = df.iloc[row_num - 2]
            with st.form("edit_form"):
                category = st.text_input("Service Category", selected_row["Service Category"])
                item = st.text_input("Item", selected_row["Item"])
                price = st.number_input("Price (USD)", value=float(selected_row["Price (USD)"]))
                turn = st.text_input("Turnaround Time", selected_row["Turnaround Time"])
                notes = st.text_area("Notes", selected_row["Notes"])
                update_btn = st.form_submit_button("🔄 Update Row")
                if update_btn:
                    ws.update(f"A{row_num}:E{row_num}", [[category, item, price, turn, notes]])
                    st.success("Row updated. Refresh the app.")

        # --------------------------
        # Delete Row
        # --------------------------
        with st.expander("❌ Delete Service Row"):
            delete_row = st.number_input("Enter Row # to Delete (Starts from 2)", min_value=2, max_value=len(df)+1)
            if st.button("🗑️ Delete"):
                ws.delete_rows(delete_row)
                st.warning(f"Row {delete_row} deleted.")

    except Exception as e:
        st.error(f"❌ Error loading sheet: {e}")
else:
    st.warning("⬅️ Upload your Google Service JSON file to continue.")
