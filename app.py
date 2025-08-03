import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO
from fpdf import FPDF

# Constants
SHEET_ID = "1WeDpcSNnfCrtx4F3bBC9osigPkzy3LXybRO6jpN7BXE"
VISIBLE_COLUMNS = ["Service Category", "Item", "Price (USD)", "Turnaround Time", "Notes"]

st.set_page_config(page_title="💼 Pricing & Services - Cards View", layout="wide")

# --- Utilities ---

def load_gsheet_data(json_data, sheet_id):
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_data, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(0)
    df = pd.DataFrame(worksheet.get_all_records())
    return worksheet, df


def export_pdf(df: pd.DataFrame) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, "Pricing & Services", ln=True, align="C")
    pdf.ln(5)
    col_widths = [40, 50, 25, 40, 35]
    headers = VISIBLE_COLUMNS

    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1)
    pdf.ln()
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 7, str(row["Service Category"]), border=1)
        pdf.cell(col_widths[1], 7, str(row["Item"]), border=1)
        pdf.cell(col_widths[2], 7, f"${row['Price (USD)']:.2f}", border=1, align='R')
        pdf.cell(col_widths[3], 7, str(row["Turnaround Time"]), border=1)
        pdf.cell(col_widths[4], 7, str(row["Notes"]), border=1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin1')


def update_row(worksheet, row_number, values):
    worksheet.update(f"A{row_number}:E{row_number}", [values])


def add_service(worksheet, values):
    worksheet.append_row(values)


def delete_row(worksheet, row_number):
    worksheet.delete_rows(row_number)


# --- Main App ---

def main():
    st.title("💼 Pricing & Services - Card View")

    st.sidebar.header("🔐 Upload Google Service Account JSON")
    json_file = st.sidebar.file_uploader("Upload your Google Service Account JSON", type=["json"])

    if not json_file:
        st.warning("⬅️ Upload your Google Service JSON file in the sidebar to continue.")
        return

    # Load JSON
    try:
        json_data = json_file.getvalue().decode("utf-8")
        json_dict = eval(json_data)
    except Exception as e:
        st.error(f"Invalid JSON: {e}")
        return

    try:
        worksheet, df = load_gsheet_data(json_dict, SHEET_ID)
    except Exception as e:
        st.error(f"❌ Error loading Google Sheet: {e}")
        return

    df.columns = df.columns.str.strip()
    df = df[VISIBLE_COLUMNS]

    # KPIs
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
        mask = filtered_df.apply(lambda r: search_term.lower() in str(r["Item"]).lower()
                                            or search_term.lower() in str(r["Notes"]).lower(), axis=1)
        filtered_df = filtered_df[mask]

    st.markdown("### 📌 Service Items")

    # Show each item in an expander card for details + inline editing
    for idx, row in filtered_df.iterrows():
        # Calculate row number in sheet (header is row 1, data start at 2)
        sheet_row_num = idx + 2
        with st.expander(f"🔹 {row['Service Category']} - {row['Item']} (Row #{sheet_row_num})", expanded=False):

            # Display fields for edit inside a form
            with st.form(f"edit_form_{sheet_row_num}"):
                col1, col2 = st.columns(2)
                category = col1.text_input("Service Category", value=row["Service Category"], key=f"cat_{sheet_row_num}")
                item = col2.text_input("Item", value=row["Item"], key=f"item_{sheet_row_num}")
                price = st.number_input("Price (USD)", min_value=0.0, value=float(row["Price (USD)"]), format="%.2f", key=f"price_{sheet_row_num}")
                turnaround = st.text_input("Turnaround Time", value=row["Turnaround Time"], key=f"turn_{sheet_row_num}")
                notes = st.text_area("Notes", value=row["Notes"], key=f"notes_{sheet_row_num}")

                update_btn = st.form_submit_button("🔄 Update this Service")
                delete_btn = st.form_submit_button("❌ Delete this Service")

                if update_btn:
                    try:
                        values = [category, item, price, turnaround, notes]
                        update_row(worksheet, sheet_row_num, values)
                        st.success(f"Row #{sheet_row_num} updated successfully. Please refresh to see changes.")
                    except Exception as e:
                        st.error(f"Failed to update row {sheet_row_num}: {e}")

                if delete_btn:
                    try:
                        delete_row(worksheet, sheet_row_num)
                        st.warning(f"Row #{sheet_row_num} deleted. Please refresh to update the view.")
                    except Exception as e:
                        st.error(f"Failed to delete row {sheet_row_num}: {e}")

    st.markdown("---")
    st.subheader("➕ Add New Service")
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
                try:
                    add_service(worksheet, [new_category, new_item, new_price, new_turnaround, new_notes])
                    st.success("Service added successfully! Please refresh the app to see the latest data.")
                except Exception as e:
                    st.error(f"Failed to add service: {e}")

    # Export buttons
    st.markdown("---")
    st.subheader("📤 Export Filtered Data")
    col_csv, col_pdf = st.columns(2)
    with col_csv:
        csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv_bytes, "services.csv", "text/csv")

    with col_pdf:
        pdf_bytes = export_pdf(filtered_df)
        st.download_button("🖨️ Download PDF", pdf_bytes, "services.pdf", "application/pdf")

    st.caption("💡 Please refresh the app (F5) after adding, updating, or deleting services to reload.")

if __name__ == "__main__":
    main()
