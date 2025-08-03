import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO
from fpdf import FPDF

# Constants
SHEET_ID = "1WeDpcSNnfCrtx4F3bBC9osigPkzy3LXybRO6jpN7BXE"
VISIBLE_COLUMNS = ["Service Category", "Item", "Price (USD)", "Turnaround Time", "Notes"]

st.set_page_config(page_title="💼 Pricing & Services", layout="wide")

# ----- Auth & Google Sheet Connection -----
def load_gsheet_data(json_data, sheet_id):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_data, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(0)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return worksheet, df

# ----- PDF Export Utility -----
def export_pdf(df: pd.DataFrame) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, "Pricing & Services", ln=True, align="C")
    pdf.ln(5)
    
    col_widths = [40, 50, 25, 40, 35]
    headers = VISIBLE_COLUMNS
    
    # Header row
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, header, border=1)
    pdf.ln()
    
    # Data rows
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 7, str(row["Service Category"]), border=1)
        pdf.cell(col_widths[1], 7, str(row["Item"]), border=1)
        pdf.cell(col_widths[2], 7, f"${row['Price (USD)']:.2f}", border=1, align='R')
        pdf.cell(col_widths[3], 7, str(row["Turnaround Time"]), border=1)
        pdf.cell(col_widths[4], 7, str(row["Notes"]), border=1)
        pdf.ln()
    
    # Instead of passing BytesIO to output(), write to BytesIO manually
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes

# ----- Main App -----
def main():
    st.title("💼 Pricing & Services Dashboard")
    st.sidebar.header("🔐 Upload Google Service Account JSON")
    
    json_file = st.sidebar.file_uploader("Upload your Google Service Account JSON", type=["json"])
    
    if not json_file:
        st.warning("⬅️ Upload your Google Service JSON file in the sidebar to continue.")
        return
    
    # Load and parse JSON securely
    try:
        json_data = json_file.getvalue().decode("utf-8")  # bytes to string
        json_dict = eval(json_data)  # careful, eval requires strict JSON but if yours is valid, can use json.loads(json_data)
    except Exception as e:
        st.error(f"Invalid JSON file or parsing error: {e}")
        return
    
    try:
        worksheet, df = load_gsheet_data(json_dict, SHEET_ID)
    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
        return
    
    # Clean dataframe columns & filter visible ones
    df.columns = df.columns.str.strip()
    df = df[VISIBLE_COLUMNS]
    
    # Show KPIs
    k1, k2, k3 = st.columns(3)
    k1.metric("🧾 Total Services", len(df))
    avg_price = df["Price (USD)"].mean()
    k2.metric("💲 Avg. Price (USD)", f"${avg_price:.2f}" if not pd.isna(avg_price) else "$0.00")
    k3.metric("🗂️ Categories", df["Service Category"].nunique())
    
    st.markdown("---")

    # Filters
    st.subheader("🔍 Filter Services")
    categories = ["All"] + sorted(df["Service Category"].unique())
    selected_cat = st.selectbox("Filter by Category", categories)
    filtered_df = df.copy()
    if selected_cat != "All":
        filtered_df = filtered_df[filtered_df["Service Category"] == selected_cat]
    
    search_term = st.text_input("Search Item or Notes")
    if search_term:
        mask = filtered_df.apply(lambda r: search_term.lower() in str(r["Item"]).lower() or search_term.lower() in str(r["Notes"]).lower(), axis=1)
        filtered_df = filtered_df[mask]
    
    st.dataframe(filtered_df, use_container_width=True)

    # ----- Download buttons -----
    col_csv, col_pdf = st.columns(2)
    with col_csv:
        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download CSV", csv_data, "services.csv", "text/csv")
    with col_pdf:
        pdf_data = export_pdf(filtered_df)
        st.download_button("🖨️ Export PDF", pdf_data, "services.pdf", "application/pdf")
    
    st.markdown("---")
    
    # ----- Add Service -----
    with st.expander("➕ Add New Service", expanded=False):
        with st.form("add_service_form"):
            col1, col2 = st.columns(2)
            new_category = col1.text_input("Service Category")
            new_item = col2.text_input("Item")
            new_price = st.number_input("Price (USD)", min_value=0.0, format="%.2f")
            new_turnaround = st.text_input("Turnaround Time")
            new_notes = st.text_area("Notes")
            submit_add = st.form_submit_button("✅ Add Service")
            if submit_add:
                if not new_category or not new_item:
                    st.error("Service Category and Item are required.")
                else:
                    # Append row
                    try:
                        worksheet.append_row([new_category, new_item, new_price, new_turnaround, new_notes])
                        st.success("Service added successfully! Please refresh the app to see updates.")
                    except Exception as e:
                        st.error(f"Failed to add new service: {e}")
    
    # ----- Edit Service -----
    with st.expander("✏️ Edit Service Row", expanded=False):
        row_num = st.number_input("Row number to edit (starting at 2)", min_value=2, max_value=len(filtered_df)+1, step=1)
        if st.button("Load row data"):
            try:
                row_data = filtered_df.iloc[row_num - 2]
                # Display fields for editing
                edit_cat = st.text_input("Service Category", row_data["Service Category"])
                edit_item = st.text_input("Item", row_data["Item"])
                edit_price = st.number_input("Price (USD)", min_value=0.0, value=float(row_data["Price (USD)"]))
                edit_turn = st.text_input("Turnaround Time", row_data["Turnaround Time"])
                edit_notes = st.text_area("Notes", row_data["Notes"])
                if st.button("🔄 Update Service"):
                    worksheet.update(f"A{row_num}:E{row_num}", [[edit_cat, edit_item, edit_price, edit_turn, edit_notes]])
                    st.success(f"Row {row_num} updated. Please refresh the app to see changes.")
            except Exception as e:
                st.error(f"Failed to load or update row: {e}")
    
    # ----- Delete Service -----
    with st.expander("❌ Delete Service Row", expanded=False):
        del_row = st.number_input("Row number to delete (starting at 2)", min_value=2, max_value=len(filtered_df)+1, step=1)
        if st.button("🗑️ Delete Row"):
            try:
                worksheet.delete_rows(del_row)
                st.warning(f"Row {del_row} deleted. Please refresh the app to see updates.")
            except Exception as e:
                st.error(f"Failed to delete row: {e}")

if __name__ == "__main__":
    main()
