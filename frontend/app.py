import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="E-Commerce Analytics", layout="wide")
st.title("🛒 Intelligent E-Commerce Customer Behavior Analytics")

# Keep our JWT wristband saved in Streamlit memory
if "jwt_token" not in st.session_state:
  st.session_state.jwt_token = ""

tab1, tab2 = st.tabs([
    "🔑 Auth #1: API Key Demo",
    "🎟️ Auth #2, #3, #4: Basic Auth + Bearer JWT Wristband",
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
        " (Store B), or type a wrong password!"
    )
    username = st.text_input("Username", value="alice")
    password = st.text_input("Password", value="passwordA", type="password")

    if st.button("1️⃣ Log In with Basic Auth & Get JWT Wristband"):
      # requests.post(..., auth=(username, password)) sends HTTP Basic Auth!
      res = requests.post(
          "http://127.0.0.1:8000/login-basic", auth=(username, password)
      )
      if res.status_code == 200:
        data = res.json()
        st.session_state.jwt_token = data["access_token"]
        st.success(f"✅ {data['message']}")
        st.write("**What is written inside your JWT Wristband:**")
        st.json(data["decoded_claims"])
      else:
        st.error(f"🚨 HTTP {res.status_code}: {res.json().get('detail')}")

  with col2:
    st.subheader("Step 2: Enter the Kitchen (Guards #3 & #4: Bearer JWT)")
    token_box = st.text_area(
        "Your Bearer JWT Wristband (you can even type a fake letter here to"
        " test tampering!):",
        value=st.session_state.jwt_token,
        height=120,
    )

    if st.button("2️⃣ Call /rfm-jwt with Bearer Wristband"):
      headers = {"Authorization": f"Bearer {token_box}"}
      res = requests.get("http://127.0.0.1:8000/rfm-jwt", headers=headers)
      if res.status_code == 200:
        data = res.json()
        st.success(
            f"✅ Wristband Valid! Logged in as **{data['logged_in_user']}** ->"
            f" Store: **{data['store_name']}** (`{data['tenant_id']}`)"
        )
        df = pd.DataFrame(data["customers"])
        st.dataframe(df, use_container_width=True)
        st.bar_chart(df.set_index("CustomerID")["Monetary"])
      else:
        st.error(f"🚨 HTTP {res.status_code}: {res.json().get('detail')}")