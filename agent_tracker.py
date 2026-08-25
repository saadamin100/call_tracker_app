import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Call Log & Fraud Detection Tracker", layout="wide", page_icon="📞")

st.title("📞 Call Log & Fraud Detection Tracker (Google Sheets Integrated)")

# Initialize Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

DEFAULT_STARTING_BALANCE = 650.0
DEFAULT_RATE_PER_MIN = 0.15

if "approved_leads" not in st.session_state:
    st.session_state.approved_leads = set()

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ Settings & Configuration")
starting_balance = st.sidebar.number_input("Starting Package Balance (PKR)", value=DEFAULT_STARTING_BALANCE, step=50.0)
rate_per_min = st.sidebar.number_input("Rate per Minute (PKR)", value=DEFAULT_RATE_PER_MIN, step=0.10)

st.sidebar.divider()
st.sidebar.subheader("📁 Upload Lead List (Excel / CSV)")
uploaded_file = st.sidebar.file_uploader("Upload Excel or CSV file", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        df_leads = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        col_names = list(df_leads.columns)
        selected_col = st.sidebar.selectbox("Select Phone Number Column", options=col_names)
        
        if selected_col:
            raw_numbers = df_leads[selected_col].dropna().astype(str).tolist()
            st.session_state.approved_leads = {
                str(num).strip().replace(".0", "").replace("-", "").replace(" ", "").replace("+92", "0")
                for num in raw_numbers
            }
            st.sidebar.success(f"✅ Loaded {len(st.session_state.approved_leads)} unique lead numbers!")
    except Exception as e:
        st.sidebar.error(f"Error loading file: {e}")

# --- FETCH EXISTING LOGS FROM GOOGLE SHEET ---
try:
    # Read sheet data
    existing_logs = conn.read(worksheet="Sheet1", ttl="0")
    existing_logs = existing_logs.dropna(how="all")
except Exception:
    existing_logs = pd.DataFrame()

if not existing_logs.empty and "Cost (PKR)" in existing_logs.columns:
    total_spent = pd.to_numeric(existing_logs["Cost (PKR)"], errors='coerce').fillna(0).sum()
    total_mins = int(pd.to_numeric(existing_logs["Duration (Mins)"], errors='coerce').fillna(0).sum())
    fraud_calls = len(existing_logs[existing_logs["Status"].astype(str).str.contains("FRAUD")])
    valid_calls = len(existing_logs) - fraud_calls
else:
    total_spent, total_mins, fraud_calls, valid_calls = 0.0, 0, 0, 0

remaining_balance = starting_balance - total_spent

# Top KPI Cards
c1, c2, c3, c4 = st.columns(4)
c1.metric("Remaining Balance", f"PKR {remaining_balance:.2f}", delta=f"-{total_spent:.2f} PKR spent" if total_spent > 0 else None, delta_color="inverse")
c2.metric("Total Spent", f"PKR {total_spent:.2f}")
c3.metric("Total Talking Time", f"{total_mins} Mins")
c4.metric("Fraud / Personal Calls", f"{fraud_calls}", delta=f"{valid_calls} Valid Calls", delta_color="normal")

st.divider()

# --- CALL ENTRY FORM ---
st.subheader("📝 Enter Completed Call Record")
with st.form("call_entry_form", clear_on_submit=True):
    col_a, col_b, col_c = st.columns(3)
    phone_input = col_a.text_input("Phone Number Dialed (e.g., 03001234567)")
    duration_input = col_b.number_input("Call Duration (Minutes)", min_value=1, value=3, step=1)
    agent_input = col_c.text_input("Agent Name", value="Agent 1")
    
    submit_btn = st.form_submit_button("Submit & Save to Google Sheets")
    
    if submit_btn:
        if phone_input:
            clean_input = phone_input.strip().replace("-", "").replace(" ", "").replace("+92", "0")
            cost = duration_input * rate_per_min
            is_fraud = clean_input not in st.session_state.approved_leads
            
            new_row = pd.DataFrame([{
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Agent Name": agent_input,
                "Phone Number": clean_input,
                "Duration (Mins)": int(duration_input),
                "Cost (PKR)": float(round(cost, 2)),
                "Status": "🚨 UNAPPROVED / FRAUD" if is_fraud else "✅ VALID LEAD CALL",
                "Is Fraud": str(is_fraud)
            }])
            
            # Merge and push to worksheet
            updated_df = pd.concat([existing_logs, new_row], ignore_index=True)
            
            try:
                # Specify worksheet="Sheet1" to resolve UnsupportedOperationError
                conn.update(worksheet="Sheet1", data=updated_df)
                st.success("✅ Entry recorded permanently in Google Sheet!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update Google Sheet: {e}")
        else:
            st.warning("Please enter a phone number.")

# --- DATA TABLE DISPLAY ---
if not existing_logs.empty:
    st.subheader("📋 Permanent Call History (From Google Sheets)")
    
    def highlight_status(val):
        return 'background-color: #ffcccc; color: #900c3f; font-weight: bold;' if "FRAUD" in str(val) else 'background-color: #e8f8f5; color: #117a65;'
    
    styled_df = existing_logs.style.map(highlight_status, subset=['Status'])
    st.dataframe(styled_df, use_container_width=True)
