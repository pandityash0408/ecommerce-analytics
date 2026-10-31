import os
import pandas as pd
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Retailer Customer Intelligence", layout="wide")

# Session state initialization
for key in ["jwt_token", "auth_code", "oauth_jwt", "m2m_jwt"]:
  if key not in st.session_state:
    st.session_state[key] = ""

# ==========================================
# SIDEBAR: RETAILER STORE SWITCHER & CSV UPLOAD
# ==========================================
st.sidebar.title("🏪 Store Owner Portal")
selected_store = st.sidebar.selectbox(
    "Select Your Connected Store:",
    [
        "Toy Kingdom (key-store-a-123)",
        "Sneaker World (key-store-b-456)",
    ],
)
active_api_key = selected_store.split("(")[1].replace(")", "")
st.sidebar.success(f"Connected with Key: `{active_api_key}`")

st.sidebar.markdown("---")
st.sidebar.subheader("📤 Upload New Store Sales (CSV)")
uploaded_file = st.sidebar.file_uploader(
    "Upload your store's CSV file (InvoiceNo, CustomerID, InvoiceDate, Quantity, UnitPrice):",
    type=["csv"],
)
if uploaded_file is not None:
  if st.sidebar.button("⚡ Clean & Load via Spark ETL"):
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
    res = requests.post(
        f"{BACKEND_URL}/etl/upload",
        headers={"X-API-Key": active_api_key},
        files=files,
    )
    if res.status_code == 200:
      etl_info = res.json()
      st.sidebar.success(
          f"✅ Loaded {etl_info['load_clean_rows_saved']} clean orders! (Removed"
          f" {etl_info['transform_dirty_rows_removed']} bad rows)"
      )
    else:
      st.sidebar.error("Failed to upload CSV.")

# ==========================================
# MAIN PAGE HEADER
# ==========================================
st.title("📊 Intelligent E-Commerce Customer Behavior & Store Advisor")
st.caption(
    "Understand how your customers shop, who is about to leave, and exact"
    " actions to grow your store revenue."
)

main_tab1, main_tab2, main_tab3, main_tab4 = st.tabs([
    "💡 1. Store Overview & Smart Reviews",
    "👥 2. Customer Behavior & Action Plan",
    "🛍️ 3. Product Bundle Recommendations",
    "🔐 4. Security (6 Auth Flows) & Spark Big Data Lab",
])

# Fetch live insights for the selected store
insights_res = requests.get(
    f"{BACKEND_URL}/store-insights", headers={"X-API-Key": active_api_key}
)
insights = insights_res.json() if insights_res.status_code == 200 else None

if insights:
  df_cust = pd.DataFrame(insights["customer_behavior"])

  # ==========================================
  # TAB 1: STORE OVERVIEW & SMART REVIEWS
  # ==========================================
  with main_tab1:
    st.subheader(f"🏪 Executive Summary for **{insights['store_name']}**")

    # Top KPI Metric Cards
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("💰 Total Revenue", f"₹{insights['kpis']['total_revenue']:,.0f}")
    k2.metric("👥 Total Customers", insights["kpis"]["total_customers"])
    k3.metric("🛒 Avg Spend / Customer", f"₹{insights['kpis']['avg_spend']:,.0f}")
    k4.metric("🏆 VIP Champions", insights["kpis"]["vip_count"])
    k5.metric("⚠️ At-Risk Customers", insights["kpis"]["at_risk_count"])

    st.markdown("### 🧠 Automated Store Reviews & Findings")
    for review in insights["store_reviews"]:
      st.info(review)

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
      st.markdown("#### 💵 Total Spend by Customer")
      st.bar_chart(df_cust.set_index("CustomerID")["Total_Spent"])
    with col_chart2:
      st.markdown("#### 🔮 Predicted 6-Month Customer Lifetime Value (CLV)")
      st.bar_chart(df_cust.set_index("CustomerID")["Predicted_6M_CLV"])

  # ==========================================
  # TAB 2: DEEP CUSTOMER BEHAVIOR & ACTION PLAN
  # ==========================================
  with main_tab2:
    st.subheader("👥 Individual Customer Behavior Reviews & Next Best Actions")
    st.write(
        "Here is what each customer is doing in your store right now and"
        " **what you should do next** to keep them buying:"
    )

    # Filter by segment
    segments = ["All Segments"] + sorted(df_cust["Segment"].unique().tolist())
    chosen_seg = st.selectbox("Filter Customers by Behavior Segment:", segments)

    filtered_df = (
        df_cust
        if chosen_seg == "All Segments"
        else df_cust[df_cust["Segment"] == chosen_seg]
    )
    st.dataframe(filtered_df, use_container_width=True)

    st.markdown("### 🔍 Customer-by-Customer Behavior Cards")
    for _, row in filtered_df.iterrows():
      with st.expander(
          f"{row['Segment']} — **{row['CustomerID']}** | Spent:"
          f" ₹{row['Total_Spent']:,.0f} | Churn Risk: {row['Churn_Risk_%']}%"
      ):
        c_left, c_right = st.columns(2)
        with c_left:
          st.markdown(f"**📋 Behavior Understanding:**\n> {row['Behavior_Understanding']}")
          st.markdown(
              f"- **Last Visit:** {row['Recency_Days']} day(s) ago\n"
              f"- **Total Orders:** {row['Orders']} orders (Avg ₹{row['Avg_Order_Value']:,.0f}/order)"
          )
        with c_right:
          st.success(f"**🎯 Recommended Action for Store Owner:**\n\n{row['Recommended_Retailer_Action']}")
          st.metric("Predicted 6-Month Value (CLV)", f"₹{row['Predicted_6M_CLV']:,.0f}")

  # ==========================================
  # TAB 3: PRODUCT RECOMMENDATIONS & FUNNEL
  # ==========================================
  with main_tab3:
    st.subheader(f"🛍️ Smart Cross-Sell & Bundle Recommendations for {insights['store_name']}")
    st.write(
        "Based on customer shopping baskets, offer these combinations at"
        " checkout to increase your store's Average Order Value:"
    )
    df_rec = pd.DataFrame(insights["product_recommendations"])
    st.table(df_rec)

    st.markdown("### 📉 Store Shopping Funnel Diagnosis")
    funnel_df = pd.DataFrame({
        "Stage": [
            "1. Visited Store",
            "2. Viewed Product",
            "3. Added to Cart",
            "4. Completed Purchase",
        ],
        "Shoppers": [1000, 620, 280, 145],
    })
    st.bar_chart(funnel_df.set_index("Stage")["Shoppers"])
    st.warning(
        "💡 **Funnel Review for Retailer:** **54% of shoppers** who add items"
        " to their cart leave without paying (`280 -> 145`). **Fix:** Enable"
        " 1-click UPI checkout and show free-shipping progress bars in the"
        " cart!"
    )

# ==========================================
# TAB 4: PROFESSOR'S 6 AUTH METHODS & SPARK ETL LAB
# ==========================================
with main_tab4:
  st.subheader("🔐 Capstone Architecture Verification: 6 Auth Methods & Apache Spark ETL")
  sub1, sub2, sub3, sub4 = st.tabs([
      "1. API Key Isolation",
      "2-4. Basic Auth + Bearer JWT",
      "5. OAuth2 Auth Code",
      "6. OAuth2 Client Credentials & Spark ETL",
  ])

  with sub1:
    test_key = st.selectbox(
        "Test Key:", ["key-store-a-123", "key-store-b-456", "wrong-hacker-key"]
    )
    if st.button("Test Guard #1 (API Key)"):
      r = requests.get(f"{BACKEND_URL}/rfm", headers={"X-API-Key": test_key})
      if r.status_code == 200:
        st.success(f"200 OK — Isolated Tenant: {r.json()['tenant_id']}")
        st.json(r.json())
      else:
        st.error(f"401 Blocked: {r.json().get('detail')}")

  with sub2:
    u = st.text_input("Basic Auth User", value="alice")
    p = st.text_input("Basic Auth Pass", value="passwordA", type="password")
    if st.button("Log In (Basic Auth) -> Issue JWT"):
      r = requests.post(f"{BACKEND_URL}/login-basic", auth=(u, p))
      if r.status_code == 200:
        st.session_state.jwt_token = r.json()["access_token"]
        st.success("Issued Bearer JWT Wristband!")
        st.json(r.json()["decoded_claims"])
      else:
        st.error(r.text)
    jwt_box = st.text_area("Bearer JWT:", value=st.session_state.jwt_token, height=80)
    if st.button("Verify Bearer JWT at /rfm-jwt"):
      r = requests.get(
          f"{BACKEND_URL}/rfm-jwt",
          headers={"Authorization": f"Bearer {jwt_box}"},
      )
      st.write(r.status_code, r.json())

  with sub3:
    if st.button("Step 1: Get 1-Time OAuth Authorization Code (vikram)"):
      r = requests.post(
          f"{BACKEND_URL}/oauth/authorize",
          data={"username": "vikram", "password": "passwordB"},
      )
      st.session_state.auth_code = r.json().get("authorization_code", "")
      st.success(f"Code: {st.session_state.auth_code}")
    if st.button("Step 2: Exchange Code for JWT at /oauth/token"):
      r = requests.post(
          f"{BACKEND_URL}/oauth/token",
          data={
              "grant_type": "authorization_code",
              "code": st.session_state.auth_code,
          },
      )
      st.write(r.status_code, r.json())

  with sub4:
    if st.button("Run OAuth2 Client Credentials (M2M) -> Call /ml/churn"):
      t = requests.post(
          f"{BACKEND_URL}/oauth/token",
          data={
              "grant_type": "client_credentials",
              "client_id": "analytics-robot",
              "client_secret": "robot-secret-999",
          },
      ).json()["access_token"]
      r = requests.get(
          f"{BACKEND_URL}/ml/churn?tenant_id=store_a",
          headers={"Authorization": f"Bearer {t}"},
      )
      st.success("Machine-to-Machine Churn Prediction Complete!")
      st.dataframe(pd.DataFrame(r.json()["predictions"]))

    sample_dirty = """InvoiceNo,CustomerID,InvoiceDate,Quantity,UnitPrice\n550001,Ananya,2026-10-30,15,120.0\n550002,,2026-10-30,5,50.0\n550003,Ananya,2026-10-29,-3,120.0"""
    if st.button("Run Demo Spark ETL + Hadoop Parquet Load"):
      files = {"file": ("dirty.csv", sample_dirty.encode("utf-8"), "text/csv")}
      r = requests.post(
          f"{BACKEND_URL}/etl/upload",
          headers={"X-API-Key": active_api_key},
          files=files,
      )
      st.json(r.json())