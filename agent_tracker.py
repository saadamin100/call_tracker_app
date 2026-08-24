import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Call Log & Fraud Detection Tracker", layout="wide", page_icon="📞")

st.title("📞 Call Log & Fraud Detection Tracker")
st.markdown("Upload your approved Lead List (Excel/CSV), track agent call durations, and automatically detect fraud or unapproved calls.")

# Default settings
DEFAULT_STARTING_BALANCE = 600.0
DEFAULT_RATE_PER_MIN = 0.60

# Initialize Session State Variables
if "approved_leads" not in st.session_state:
    st.session_state.approved_leads = set()

if "logs" not in st.session_state:
    st.session_state.logs = []

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ Settings & Configuration")
starting_balance = st.sidebar.number_input("Starting Package Balance (PKR)", value=DEFAULT_STARTING_BALANCE, step=50.0)
rate_per_min = st.sidebar.number_input("Rate per Minute (PKR)", value=DEFAULT_RATE_PER_MIN, step=0.10)

st.sidebar.divider()
st.sidebar.subheader("📁 Upload Lead List (Excel / CSV)")
uploaded_file = st.sidebar.file_uploader("Upload Excel or CSV file", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_leads = pd.read_csv(uploaded_file)
        else:
            df_leads = pd.read_excel(uploaded_file)
        
        # Display column selection if multiple columns exist
        col_names = list(df_leads.columns)
        selected_col = st.sidebar.selectbox("Select Phone Number Column", options=col_names)
        
        if selected_col:
            # Clean and normalize phone numbers (remove spaces, dashes, decimals)
            raw_numbers = df_leads[selected_col].dropna().astype(str).tolist()
            cleaned_numbers = {
                str(num).strip().replace(".0", "").replace("-", "").replace(" ", "").replace("+92", "0")
                for num in raw_numbers
            }
            st.session_state.approved_leads = cleaned_numbers
            st.sidebar.success(f"✅ Loaded {len(cleaned_numbers)} unique lead numbers!")
    except Exception as e:
        st.sidebar.error(f"Error loading file: {e}")

# Display Loaded Leads Summary in Sidebar
if st.session_state.approved_leads:
    st.sidebar.info(f"📋 Total Active Approved Leads: **{len(st.session_state.approved_leads)}**")
else:
    st.sidebar.warning("⚠️ No Lead List uploaded yet. All calls will be flagged as unapproved until uploaded.")

# --- METRICS & CALCULATIONS ---
if st.session_state.logs:
    df_logs = pd.DataFrame(st.session_state.logs)
    total_spent = df_logs["Cost (PKR)"].sum()
    total_mins = df_logs["Duration (Mins)"].sum()
    fraud_calls = len(df_logs[df_logs["Is Fraud"] == True])
    valid_calls = len(df_logs[df_logs["Is Fraud"] == False])
else:
    total_spent = 0.0
    total_mins = 0
    fraud_calls = 0
    valid_calls = 0

remaining_balance = starting_balance - total_spent

# Top KPI Dashboard Cards
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
    
    submit_btn = st.form_submit_button("Submit & Deduct Balance")
    
    if submit_btn:
        if phone_input:
            # Normalize input phone number
            clean_input = phone_input.strip().replace("-", "").replace(" ", "").replace("+92", "0")
            cost = duration_input * rate_per_min
            
            # Check against approved lead list
            is_fraud = clean_input not in st.session_state.approved_leads
            
            log_entry = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Agent Name": agent_input,
                "Phone Number": clean_input,
                "Duration (Mins)": duration_input,
                "Cost (PKR)": round(cost, 2),
                "Status": "🚨 UNAPPROVED / FRAUD" if is_fraud else "✅ VALID LEAD CALL",
                "Is Fraud": is_fraud
            }
            
            st.session_state.logs.append(log_entry)
            st.rerun()
        else:
            st.warning("Please enter a phone number.")

# --- DATA TABLE & HIGHLIGHTING ---
if st.session_state.logs:
    st.subheader("📋 Real-time Call Log History")
    df_display = pd.DataFrame(st.session_state.logs)
    
    # Custom Row Styling: Highlight Fraud in Light Red
    def highlight_status(val):
        if "FRAUD" in str(val):
            return 'background-color: #ffcccc; color: #900c3f; font-weight: bold;'
        return 'background-color: #e8f8f5; color: #117a65;'

    styled_df = df_display.style.applymap(highlight_status, subset=['Status'])
    st.dataframe(styled_df, use_container_width=True)
    
    # Download Log Button
    csv_data = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Call Logs as CSV", csv_data, "call_logs_export.csv", "text/csv")