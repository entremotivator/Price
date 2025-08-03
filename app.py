import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode, JsCode
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO
from fpdf import FPDF

st.set_page_config(page_title="💼 Pricing & Services", layout="wide")

# Constants
SHEET_ID = "1WeDpcSNnfCrtx4F3bBC9osigPkzy3LXybRO6jpN7BXE"
VISIBLE_COLUMNS = ["Service Category", "Item", "Price (USD)", "Turnaround Time", "Notes"]

st.sidebar.header("🔐 Google Auth")
json_file = st.sidebar.file_uploader(
    "Upload your Google Service Account .json", type="json", key="json_upload"
)

def get_gsheet_data(sheet_id, worksheet_index=0):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(eval(json_file.read()), scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(worksheet_index)
    df = pd.DataFrame(worksheet.get_all_records())
    return worksheet, df

def export_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt="Pricing & Services", ln=True, align='C')
    for idx, row in df.iterrows():
        text = " | ".join([f"{v}" for v in row.values])
        pdf.cell(200, 8, txt=text, ln=True)
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    return pdf_buffer.getvalue()

def aggrid_table(df, selection_mode="multiple"):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination()
    gb.configure_side_bar()
    gb.configure_columns(["Price (USD)"], type=["numericColumn", "customNumericFormat"], precision=2)
    gb.configure_default_column(editable=True, groupable=True, filter=True, sortable=True, resizable=True)
    gb.configure_selection(selection_mode=selection_mode, use_checkbox=True)
    gb.configure_grid_options(domLayout='autoHeight')
    grid = AgGrid(
        df,
        gridOptions=gb.build(),
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=True,
        height=500,
        theme="streamlit"
    )
    return grid

# App Logic
if json_file:
    try:
        ws, df = get_gsheet_data(SHEET_ID)
        df.columns = df.columns.str.strip()
        df = df[VISIBLE_COLUMNS]

        st.title("💼 Pricing & Services Dashboard")

        # KPIs
        metric1, metric2, metric3 = st.columns(3)
        metric1.metric("🧾 Total Services", len(df))
        metric2.metric("💲 Avg. Price (USD)", f"${df['Price (USD)'].mean():.2f}")
        metric3.metric("🗂️ Categories", df["Service Category"].nunique())
        st.markdown("---")

        # Filter Panel
        with st.expander("🔍 Advanced Filtering & Search", expanded=True):
            category_options = ["All"] + sorted(df["Service Category"].unique())
            col_f1, col_f2 = st.columns([2,2])
            category_f = col_f1.selectbox("Service Category", category_options, index=0)
            search_str = col_f2.text_input("Search (across all columns)")
            # Filter logic
            filter_df = df.copy()
            if category_f != "All":
                filter_df = filter_df[filter_df["Service Category"] == category_f]
            if search_str:
                filter_df = filter_df[filter_df.apply(lambda row: search_str.lower() in str(row).lower(), axis=1)]

        # AgGrid Table + Actions
        st.markdown("#### 📋 Service List (editable table, click cells to edit)")
        grid_response = aggrid_table(filter_df, selection_mode="multiple")

        st.markdown("---")

        # Download/Export options
        exp_col1, exp_col2, exp_col3 = st.columns([1,1,1])
        exp_col1.download_button("⬇️ CSV", filter_df.to_csv(index=False), "services.csv", "text/csv")
        excel_bytes = BytesIO()
        filter_df.to_excel(excel_bytes, index=False)
        exp_col2.download_button("⬇️ XLSX", excel_bytes.getvalue(), "services.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        pdf_bytes = export_pdf(filter_df)
        exp_col3.download_button("🖨️ PDF", pdf_bytes, "services.pdf", "application/pdf")

        st.info("Tip: Use the checkboxes to select rows for editing or deletion below.")

        # Add New Service
        with st.expander("➕ Add New Service"):
            with st.form("add_service_form"):
                ac1, ac2, ac3 = st.columns([2,3,2])
                new_cat = ac1.text_input("Service Category")
                new_item = ac2.text_input("Item/Description")
                new_price = ac3.number_input("Price (USD)", min_value=0.0, step=1.0)
                new_turn = ac1.text_input("Turnaround Time")
                new_notes = ac2.text_input("Notes")
                submit_add = st.form_submit_button("✅ Add Service")
                if submit_add:
                    ws.append_row([new_cat, new_item, new_price, new_turn, new_notes])
                    st.success("Service added. Refresh to see it in the table.")

        # Inline/Batch Update
        with st.expander("✏️ Batch Edit Services (Selected Rows)", expanded=False):
            if grid_response['selected_rows']:
                selected = pd.DataFrame(grid_response['selected_rows'])
                st.dataframe(selected)
                st.info("After making edits in the table above, click the 'Update Rows' button below.")
                if st.button("🔄 Update Selected Rows in Google Sheet"):
                    for _, row in selected.iterrows():
                        # Find row index in main DataFrame (minus header offset, index starts at 2)
                        main_idx = df[(df["Service Category"] == row["Service Category"]) & 
                                      (df["Item"] == row["Item"])].index
                        if not main_idx.empty:
                            ws.update(f"A{main_idx[0]+2}:E{main_idx[0]+2}", [row.values[:5]])
                    st.success("Rows updated! Refresh to view changes.")
            else:
                st.info("Select one or more rows via the left checkboxes in the table above.")

        # Delete Service
        with st.expander("❌ Batch Delete Selected Services"):
            if grid_response["selected_rows"]:
                del_rows = pd.DataFrame(grid_response["selected_rows"])
                if st.button(f"🗑️ DELETE {len(del_rows)} Selected Row(s) !!"):
                    # Remember, Google Sheet row numbers start from 2 (header is row 1)
                    for _, sel in del_rows.iterrows():
                        idx = df[(df["Service Category"] == sel["Service Category"]) & (df["Item"] == sel["Item"])].index
                        if not idx.empty:
                            ws.delete_rows(idx[0]+2)
                    st.warning("Selected rows/records deleted! Refresh to update the view.")
            else:
                st.info("Select one or more rows using checkboxes before deleting.")

        st.caption("Powered by Streamlit, Google Sheets & st-aggrid. Refresh (F5) after edit/add/remove to reload data.")

    except Exception as e:
        st.error(f"❌ Error: {e}")
else:
    st.warning("⬅️ Upload your Google Service JSON file in the sidebar to continue.")



