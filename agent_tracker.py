import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Call Log & Minutes Tracker", layout="wide", page_icon="📞")

st.title("📞 Cold Calling & Package Minutes Tracker")

# --- INITIALIZE GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- DEFAULT PACKAGE ALLOWANCES ---
DEFAULT_ONNET_MINS = 2000
DEFAULT_OFFNET_MINS = 100

# --- PAKISTAN TELECOM PREFIX RULES ---
JAZZ_PREFIXES = ('0300', '0301', '0302', '0303', '0304', '0305', '0306', '0307', '0308', '0309', '0320', '0321', '0322', '0323', '0324', '0325')
ZONG_PREFIXES = ('0310', '0311', '0312', '0313', '0314', '0315', '0316', '0317', '0318', '0319')
TELENOR_PREFIXES = ('0340', '0341', '0342', '0343', '0344', '0345', '0346', '0347', '0348', '0349')
UFONE_PREFIXES = ('0330', '0331', '0332', '0333', '0334', '0335', '0336', '0337')

def detect_network(phone_num):
    clean = phone_num.strip().replace("-", "").replace(" ", "").replace("+92", "0")
    if clean.startswith(JAZZ_PREFIXES):
        return "Jazz (On-Net)", "On-Net"
    elif clean.startswith(ZONG_PREFIXES):
        return "Zong (Off-Net)", "Off-Net"
    elif clean.startswith(TELENOR_PREFIXES):
        return "Telenor (Off-Net)", "Off-Net"
    elif clean.startswith(UFONE_PREFIXES):
        return "Ufone (Off-Net)", "Off-Net"
    else:
        return "Other/Landline (Off-Net)", "Off-Net"

if "approved_leads" not in st.session_state:
    st.session_state.approved_leads = set()

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ Package Limits Configuration")
total_onnet_limit = st.sidebar.number_input("Total On-Net Minutes Limit (Jazz)", value=DEFAULT_ONNET_MINS, step=50)
total_offnet_limit = st.sidebar.number_input("Total Off-Net Minutes Limit (Other)", value=DEFAULT_OFFNET_MINS, step=10)

st.sidebar.divider()
st.sidebar.subheader("📁 Upload Approved Lead List (CSV/Excel)")
uploaded_file = st.sidebar.file_uploader("Upload Lead Sheet", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        df_leads = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        col_names = list(df_leads.columns)
        selected_col = st.sidebar.selectbox("Select Phone Column", options=col_names)
        
        if selected_col:
            raw_numbers = df_leads[selected_col].dropna().astype(str).tolist()
            st.session_state.approved_leads = {
                str(num).strip().replace(".0", "").replace("-", "").replace(" ", "").replace("+92", "0")
                for num in raw_numbers
            }
            st.sidebar.success(f"✅ Loaded {len(st.session_state.approved_leads)} Approved Leads!")
    except Exception as e:
        st.sidebar.error(f"File Loading Error: {e}")

# --- READ LOGS FROM GOOGLE SHEET ---
try:
    existing_logs = conn.read(worksheet="Sheet1", ttl="0")
    existing_logs = existing_logs.dropna(how="all")
except Exception:
    existing_logs = pd.DataFrame()

onnet_used = 0
offnet_used = 0
fraud_calls = 0
valid_calls = 0

if not existing_logs.empty and "Network Type" in existing_logs.columns:
    for _, row in existing_logs.iterrows():
        dur = int(pd.to_numeric(row.get("Duration (Mins)", 0), errors='coerce') or 0)
        net_type = str(row.get("Network Type", ""))
        status = str(row.get("Status", ""))
        
        if "FRAUD" in status:
            fraud_calls += 1
        else:
            valid_calls += 1

        if "On-Net" in net_type:
            onnet_used += dur
        elif "Off-Net" in net_type:
            offnet_used += dur

rem_onnet = total_onnet_limit - onnet_used
rem_offnet = total_offnet_limit - offnet_used

# --- METRIC CARDS ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Remaining On-Net Mins", f"{rem_onnet} Mins", delta=f"-{onnet_used} Mins used", delta_color="inverse")
c2.metric("Remaining Off-Net Mins", f"{rem_offnet} Mins", delta=f"-{offnet_used} Mins used", delta_color="inverse")
c3.metric("Total Calls Conducted", f"{len(existing_logs)}")
c4.metric("Unapproved / Fraud Calls", f"{fraud_calls}", delta=f"{valid_calls} Valid Calls", delta_color="normal")

st.divider()

# --- CALL ENTRY FORM ---
st.subheader("📝 Enter Call Details")

with st.form("call_entry_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    phone_input = col_a.text_input("Phone Number Dialed (e.g., 03001234567)")
    agent_input = col_b.text_input("Agent Name", value="Agent 1")
    
    col_c, col_d = st.columns(2)
    
    # Pre-select network based on entered prefix
    default_index = 0
    if phone_input:
        _, detected_type = detect_network(phone_input)
        if "Off-Net" in detected_type:
            default_index = 1
            
    network_choice = col_c.selectbox(
        "Network (Auto-Detected, change if converted/ported)",
        options=["Jazz (On-Net)", "Zong (Off-Net)", "Telenor (Off-Net)", "Ufone (Off-Net)", "Other / PTCL (Off-Net)"],
        index=default_index
    )
    
    duration_input = col_d.number_input("Call Duration (Minutes)", min_value=0, value=1, step=1)
    
    submit_btn = st.form_submit_button("Submit & Deduct Minutes")
    
    if submit_btn:
        if phone_input:
            clean_input = phone_input.strip().replace("-", "").replace(" ", "").replace("+92", "0")
            final_type = "On-Net" if "On-Net" in network_choice else "Off-Net"
            
            # Fraud detection logic against uploaded leads
            if len(st.session_state.approved_leads) > 0:
                is_fraud = clean_input not in st.session_state.approved_leads
                status_msg = "🚨 UNAPPROVED / FRAUD" if is_fraud else ("🚫 NO ANSWER" if duration_input == 0 else "✅ VALID LEAD CALL")
            else:
                is_fraud = False
                status_msg = "🚫 NO ANSWER" if duration_input == 0 else "✅ VALID CALL"
            
            new_row = pd.DataFrame([{
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Agent Name": agent_input,
                "Phone Number": clean_input,
                "Network": network_choice,
                "Network Type": final_type,
                "Duration (Mins)": int(duration_input),
                "Status": status_msg,
                "Is Fraud": str(is_fraud)
            }])
            
            updated_df = pd.concat([existing_logs, new_row], ignore_index=True)
            
            try:
                conn.update(worksheet="Sheet1", data=updated_df)
                st.success(f"✅ Call Logged! Deducted **{duration_input} {final_type} Minute(s)**.")
                st.rerun()
            except Exception as e:
                st.error(f"Google Sheet update fail ho gaya: {e}")
        else:
            st.warning("Meherbani karke phone number enter karein.")

# --- DATA TABLE DISPLAY ---
if not existing_logs.empty:
    st.subheader("📋 Permanent Call History (Google Sheets)")
    
    def highlight_status(val):
        if "FRAUD" in str(val):
            return 'background-color: #ffcccc; color: #900c3f; font-weight: bold;'
        elif "NO ANSWER" in str(val):
            return 'background-color: #fff3cd; color: #856404; font-weight: bold;'
        else:
            return 'background-color: #e8f8f5; color: #117a65;'
    
    styled_df = existing_logs.style.map(highlight_status, subset=['Status'])
    st.dataframe(styled_df, use_container_width=True)
