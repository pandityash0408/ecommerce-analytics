import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="E-Commerce Analytics", layout="wide")
st.title("🛒 Intelligent E-Commerce Customer Behavior Analytics")

if "jwt_token" not in st.session_state:
  st.session_state.jwt_token = ""
if "auth_code" not in st.session_state:
  st.session_state.auth_code = ""
if "oauth_jwt" not in st.session_state:
  st.session_state.oauth_jwt = ""
if "m2m_jwt" not in st.session_state:
  st.session_state.m2m_jwt = ""

tab1, tab2, tab3, tab4 = st.tabs([
    "🔑 1. API Key",
    "🎟️ 2-4. Basic + Bearer + JWT",
    "🌐 5. OAuth2 Auth Code Flow",
    "🤖 6. OAuth2 Client Credentials (ML Churn)",
])

# ==========================================
# TAB 1: API KEY DEMO
# ==========================================
with tab1:
  st.subheader("Guard #1: API Key Authentication (`X-API-Key`)")
  selected_option = st.selectbox(
      "Choose a Store Keycard to test:",
      [
          "Store A - Toy Kingdom (key-store-a-123)",
          "Store B - Sneaker World (key-store-b-456)",
          "Fake Hacker Key (wrong-key-999)",
      ],
  )
  api_key = selected_option.split("(")[1].replace(")", "")
  st.code(f"GET /rfm\nX-API-Key: {api_key}")

  if st.button("Load Customers with API Key"):
    response = requests.get(
        "http://127.0.0.1:8000/rfm", headers={"X-API-Key": api_key}
    )
    if response.status_code == 200:
      data = response.json()
      st.success(
          f"✅ Access Granted via **{data['auth_method']}**! Store:"
          f" **{data['store_name']}** (`{data['tenant_id']}`)"
      )
      df = pd.DataFrame(data["customers"])
      st.dataframe(df, use_container_width=True)
      st.bar_chart(df.set_index("CustomerID")["Monetary"])
    else:
      st.error(
          f"🚨 HTTP {response.status_code}: {response.json().get('detail')}"
      )

# ==========================================
# TAB 2: BASIC AUTH -> BEARER JWT DEMO
# ==========================================
with tab2:
  col1, col2 = st.columns(2)
  with col1:
    st.subheader("Step 1: Ticket Booth (Guard #2: Basic Auth)")
    st.write(
        "Try **`alice` / `passwordA`** (Store A) or **`vikram` / `passwordB`**"
        " (Store B)."
    )
    username = st.text_input("Username", value="alice")
    password = st.text_input("Password", value="passwordA", type="password")

    if st.button("1️⃣ Log In with Basic Auth & Get JWT Wristband"):
      res = requests.post(
          "http://127.0.0.1:8000/login-basic", auth=(username, password)
      )
      if res.status_code == 200:
        data = res.json()
        st.session_state.jwt_token = data["access_token"]
        st.success(f"✅ {data['message']}")
        st.json(data["decoded_claims"])
      else:
        st.error(f"🚨 HTTP {res.status_code}: {res.json().get('detail')}")

  with col2:
    st.subheader("Step 2: Enter the Kitchen (Guards #3 & #4: Bearer JWT)")
    token_box = st.text_area(
        "Your Bearer JWT Wristband:",
        value=st.session_state.jwt_token,
        height=120,
    )
    if st.button("2️⃣ Call /rfm-jwt with Bearer Wristband"):
      res = requests.get(
          "http://127.0.0.1:8000/rfm-jwt",
          headers={"Authorization": f"Bearer {token_box}"},
      )
      if res.status_code == 200:
        data = res.json()
        st.success(
            f"✅ Wristband Valid! User: **{data['logged_in_user']}** | Store:"
            f" **{data['store_name']}**"
        )
        df = pd.DataFrame(data["customers"])
        st.dataframe(df, use_container_width=True)
        st.bar_chart(df.set_index("CustomerID")["Monetary"])
      else:
        st.error(f"🚨 HTTP {res.status_code}: {res.json().get('detail')}")

# ==========================================
# TAB 3: OAUTH 2.0 AUTHORIZATION CODE FLOW
# ==========================================
with tab3:
  st.subheader("Guard #5: OAuth 2.0 Authorization Code Flow (2-Step Login)")
  c1, c2, c3 = st.columns(3)

  with c1:
    st.markdown("#### Step 1: Get 1-Time Code")
    oa_user = st.text_input("OAuth User", value="vikram")
    oa_pass = st.text_input("OAuth Password", value="passwordB", type="password")
    if st.button("1️⃣ Authorize & Get Code"):
      res = requests.post(
          "http://127.0.0.1:8000/oauth/authorize",
          data={"username": oa_user, "password": oa_pass},
      )
      if res.status_code == 200:
        st.session_state.auth_code = res.json()["authorization_code"]
        st.success(f"✅ Got 1-time code: `{st.session_state.auth_code}`")
      else:
        st.error(f"🚨 {res.json().get('detail')}")

  with c2:
    st.markdown("#### Step 2: Trade Code for JWT")
    code_input = st.text_input(
        "1-Time Authorization Code:", value=st.session_state.auth_code
    )
    if st.button("2️⃣ Exchange Code at /oauth/token"):
      res = requests.post(
          "http://127.0.0.1:8000/oauth/token",
          data={"grant_type": "authorization_code", "code": code_input},
      )
      if res.status_code == 200:
        data = res.json()
        st.session_state.oauth_jwt = data["access_token"]
        st.success("✅ Exchanged code for OAuth JWT! (Try clicking again—the code is now used up!)")
        st.json(data["decoded_claims"])
      else:
        st.error(f"🚨 HTTP {res.status_code}: {res.json().get('detail')}")

  with c3:
    st.markdown("#### Step 3: Load Store Data")
    if st.button("3️⃣ Call /rfm-jwt with OAuth Token"):
      res = requests.get(
          "http://127.0.0.1:8000/rfm-jwt",
          headers={"Authorization": f"Bearer {st.session_state.oauth_jwt}"},
      )
      if res.status_code == 200:
        data = res.json()
        st.success(f"✅ Loaded **{data['store_name']}** via **{data['auth_method']}**!")
        st.dataframe(pd.DataFrame(data["customers"]), use_container_width=True)
      else:
        st.error(f"🚨 HTTP {res.status_code}: {res.json().get('detail')}")

# ==========================================
# TAB 4: OAUTH 2.0 CLIENT CREDENTIALS (M2M)
# ==========================================
with tab4:
  st.subheader(
      "Guard #6: OAuth 2.0 Client Credentials Flow (Analytics Robot -> ML Churn"
      " Service)"
  )
  col_a, col_b = st.columns(2)

  with col_a:
    st.markdown("#### Step 1: Robot Authenticates")
    client_id = st.text_input("Robot Client ID", value="analytics-robot")
    client_secret = st.text_input(
        "Robot Client Secret", value="robot-secret-999", type="password"
    )
    if st.button("1️⃣ Get Machine-to-Machine JWT"):
      res = requests.post(
          "http://127.0.0.1:8000/oauth/token",
          data={
              "grant_type": "client_credentials",
              "client_id": client_id,
              "client_secret": client_secret,
          },
      )
      if res.status_code == 200:
        data = res.json()
        st.session_state.m2m_jwt = data["access_token"]
        st.success("✅ Robot authenticated! Scope `ml:predict` granted.")
        st.json(data["decoded_claims"])
      else:
        st.error(f"🚨 HTTP {res.status_code}: {res.json().get('detail')}")

  with col_b:
    st.markdown("#### Step 2: Call ML Churn Service (`/ml/churn`)")
    target_store = st.selectbox("Select Store to Predict Churn:", ["store_a", "store_b"])
    if st.button("2️⃣ Run ML Churn Prediction"):
      res = requests.get(
          f"http://127.0.0.1:8000/ml/churn?tenant_id={target_store}",
          headers={"Authorization": f"Bearer {st.session_state.m2m_jwt}"},
      )
      if res.status_code == 200:
        data = res.json()
        st.success(
            f"✅ ML Service responded to **{data['called_by_robot']}** via"
            f" **{data['auth_flow']}**!"
        )
        st.dataframe(pd.DataFrame(data["predictions"]), use_container_width=True)
      else:
        st.error(f"🚨 HTTP {res.status_code}: {res.json().get('detail')}")