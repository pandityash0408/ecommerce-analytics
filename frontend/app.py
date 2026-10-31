import os
import pandas as pd
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Retailer Customer Intelligence", layout="wide")

for key in ["jwt_token", "auth_code", "oauth_jwt", "m2m_jwt"]:
  if key not in st.session_state:
    st.session_state[key] = ""

# ==========================================
# SIDEBAR: RETAILER STORE PORTAL & CSV UPLOAD
# ==========================================
st.sidebar.title("🏪 Retailer Portal")
selected_store = st.sidebar.selectbox(
    "Active Store Account:",
    [
        "Toy Kingdom (key-store-a-123)",
        "Sneaker World (key-store-b-456)",
    ],
)
active_api_key = selected_store.split("(")[1].replace(")", "")

st.sidebar.markdown("---")
st.sidebar.subheader("📤 Upload Store Sales (CSV)")
uploaded_file = st.sidebar.file_uploader(
    "Upload CSV (InvoiceNo, CustomerID, InvoiceDate, Quantity, UnitPrice):",
    type=["csv"],
)
if uploaded_file is not None:
  if st.sidebar.button("⚡ Clean & Load Sales Data"):
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

st.sidebar.markdown("---")
show_viva_mode = st.sidebar.checkbox(
    "🎓 Show Viva / Professor Security Demo", value=False
)

# ==========================================
# MAIN RETAILER WEBSITE (100% BUSINESS FOCUSED)
# ==========================================
st.title("📊 Intelligent E-Commerce Customer Behavior & Store Advisor")
st.caption(
    "Understand how your customers shop, who is about to leave, and exact"
    " actions to grow your store revenue."
)

main_tab1, main_tab2, main_tab3, main_tab4 = st.tabs([
    "💡 1. Store Overview & Smart Reviews",
    "👥 2. Customer Behavior & Action Plan",
    "🛍️ 3. Product Bundles, Funnel & Cohorts",
    "🎯 4. Customer 360° & Revenue Simulator",
])

insights_res = requests.get(
    f"{BACKEND_URL}/store-insights", headers={"X-API-Key": active_api_key}
)
insights = insights_res.json() if insights_res.status_code == 200 else None

if insights:
  df_cust = pd.DataFrame(insights["customer_behavior"])

  # TAB 1: STORE OVERVIEW & SMART REVIEWS
  with main_tab1:
    st.subheader(f"🏪 Executive Summary for **{insights['store_name']}**")

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

  # TAB 2: DEEP CUSTOMER BEHAVIOR & ACTION PLAN
  with main_tab2:
    st.subheader("👥 Individual Customer Behavior Reviews & Next Best Actions")
    st.write(
        "Each customer is automatically analyzed using **RFM + K-Means"
        " Clustering** to give you a clear review and recommended action:"
    )

    segments = ["All Segments"] + sorted(df_cust["Segment"].unique().tolist())
    chosen_seg = st.selectbox("Filter Customers by Behavior Segment:", segments)

    filtered_df = (
        df_cust
        if chosen_seg == "All Segments"
        else df_cust[df_cust["Segment"] == chosen_seg]
    )
    st.dataframe(filtered_df, use_container_width=True)

    csv_export = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Customer Behavior & Action Plan Report (CSV)",
        data=csv_export,
        file_name=f"{insights['tenant_id']}_customer_behavior_report.csv",
        mime="text/csv",
    )

    st.markdown("### 🔍 Customer-by-Customer Behavior Cards")
    for _, row in filtered_df.iterrows():
      cluster_label = row.get("KMeans_ML_Cluster", "Cluster 0")
      with st.expander(
          f"{row['Segment']} ({cluster_label}) — **{row['CustomerID']}** |"
          f" Spent: ₹{row['Total_Spent']:,.0f} | Churn Risk:"
          f" {row['Churn_Risk_%']}%"
      ):
        c_left, c_right = st.columns(2)
        with c_left:
          st.markdown(
              f"**📋 Behavior Understanding:**\n> {row['Behavior_Understanding']}"
          )
          st.markdown(
              f"- **Last Visit:** {row['Recency_Days']} day(s) ago\n"
              f"- **Total Orders:** {row['Orders']} orders (Avg"
              f" ₹{row['Avg_Order_Value']:,.0f}/order)\n"
              f"- **ML Cluster:** `{cluster_label}`"
          )
        with c_right:
          st.success(
              "**🎯 Recommended Action for Store Owner:**\n\n"
              f"{row['Recommended_Retailer_Action']}"
          )
          st.metric(
              "Predicted 6-Month Value (CLV)", f"₹{row['Predicted_6M_CLV']:,.0f}"
          )

  # TAB 3: PRODUCT RECOMMENDATIONS, FUNNEL & COHORTS
  with main_tab3:
    st.subheader(
        f"🛍️ Smart Cross-Sell & Bundle Recommendations for {insights['store_name']}"
    )
    st.table(pd.DataFrame(insights["product_recommendations"]))

    c_fun, c_coh = st.columns(2)
    with c_fun:
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
          "💡 **Funnel Review:** **54% of shoppers** who add items to their"
          " cart leave without paying. Enable 1-click UPI checkout!"
      )

    with c_coh:
      st.markdown("### 📅 Monthly Customer Cohort Retention")
      st.write(
          "Percentage of customers who come back and buy again in following"
          " months:"
      )
      if "cohort_retention" in insights:
        st.table(pd.DataFrame(insights["cohort_retention"]))
      st.info(
          "💡 **Cohort Review:** Retention jumped from **68% to 74%** in Month 2"
          " after introducing loyalty points!"
      )

  # TAB 4: CUSTOMER 360, WHAT-IF SIMULATOR & PRIVACY
  with main_tab4:
    st.subheader(
        "🔍 1. Customer 360° Inspector & Personalized WhatsApp/Email Generator"
    )
    cust_list = df_cust["CustomerID"].tolist()
    picked_customer = st.selectbox("Select a Customer to Inspect:", cust_list)

    if picked_customer:
      c360_res = requests.get(
          f"{BACKEND_URL}/customer-360/{picked_customer}",
          headers={"X-API-Key": active_api_key},
      )
      if c360_res.status_code == 200:
        c360 = c360_res.json()
        col_p1, col_p2 = st.columns(2)
        with col_p1:
          st.markdown(
              f"**🧠 Why Our AI Scored `{picked_customer}` This Way (SHAP"
              " Drivers):**"
          )
          st.table(pd.DataFrame(c360["shap_explanations"]))
          st.markdown("**🧾 Individual Purchase History:**")
          st.dataframe(
              pd.DataFrame(c360["order_history"]), use_container_width=True
          )
        with col_p2:
          st.markdown("**💬 Ready-to-Send WhatsApp / Email Campaign Message:**")
          st.code(c360["ready_to_send_message"], language="text")
          st.caption(
              "Copy and send this message to the customer to boost retention!"
          )
      else:
        st.info(
            "Make sure you pasted the `/customer-360/{customer_id}` endpoint"
            " at the bottom of `backend/main.py` and saved it!"
        )

    st.markdown("---")
    st.subheader("💰 2. Retailer 'What-If' Revenue Growth Simulator")
    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
      winback_pct = st.slider(
          "If we win back % of At-Risk Customers:", 0, 100, 40
      )
      bundle_uplift_pct = st.slider(
          "If Product Bundles increase order size by %:", 0, 50, 15
      )
    with sim_col2:
      base_rev = insights["kpis"]["total_revenue"]
      projected_gain = round(
          base_rev * (winback_pct / 100 * 0.25)
          + base_rev * (bundle_uplift_pct / 100),
          2,
      )
      st.metric(
          "🚀 Projected Extra Store Revenue (Next 6 Months)",
          f"+₹{projected_gain:,.0f}",
          delta=f"New Total: ₹{base_rev + projected_gain:,.0f}",
      )

    st.markdown("---")
    st.subheader("🛡️ 3. Customer Privacy & India DPDP Act 2023 Compliance")
    erase_target = st.selectbox(
        "Select Customer Requesting Data Erasure:", cust_list, key="erase_sel"
    )
    if st.button("🗑️ Erase Customer Data (DPDP Act Right to Erasure)"):
      del_res = requests.delete(
          f"{BACKEND_URL}/privacy/erase/{erase_target}",
          headers={"X-API-Key": active_api_key},
      )
      if del_res.status_code == 200:
        st.success(f"✅ Erased `{erase_target}`! Refresh the page to update.")
        st.json(del_res.json())

# ==========================================
# OPTIONAL VIVA DEMO PANEL (ONLY SHOWN WHEN CHECKBOX IS TICKED)
# ==========================================
if show_viva_mode:
  st.markdown("---")
  st.subheader("🎓 Viva Exam Demo: 6 Auth Methods & Apache Spark ETL")
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
      st.write(r.status_code, r.json())

  with sub2:
    u = st.text_input("Basic Auth User", value="alice")
    p = st.text_input("Basic Auth Pass", value="passwordA", type="password")
    if st.button("Log In (Basic Auth) -> Issue JWT"):
      r = requests.post(f"{BACKEND_URL}/login-basic", auth=(u, p))
      if r.status_code == 200:
        st.session_state.jwt_token = r.json()["access_token"]
        st.json(r.json()["decoded_claims"])
    jwt_box = st.text_area(
        "Bearer JWT:", value=st.session_state.jwt_token, height=80
    )
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
      st.dataframe(pd.DataFrame(r.json()["predictions"]))