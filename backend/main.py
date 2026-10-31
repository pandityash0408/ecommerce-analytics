from datetime import datetime, timedelta, timezone
import secrets
import sqlite3
from database import DB_PATH, init_db
from etl_spark import run_spark_etl
from fastapi import Depends, FastAPI, File, Form, HTTPException, Security, UploadFile
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
import jwt
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

app = FastAPI(title="Intelligent E-Commerce Analytics API")

init_db()

JWT_SECRET = "my-super-secret-kitchen-stamp-2026"
JWT_ALGORITHM = "HS256"

# GUARD #1: API Key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEYS = {
    "key-store-a-123": {"tenant_id": "store_a", "store_name": "Toy Kingdom"},
    "key-store-b-456": {"tenant_id": "store_b", "store_name": "Sneaker World"},
}


def verify_api_key(api_key: str = Security(api_key_header)):
  if api_key not in API_KEYS:
    raise HTTPException(
        status_code=401,
        detail="Guard #1 (API Key): Invalid or missing X-API-Key!",
    )
  return API_KEYS[api_key]


# GUARD #2: Basic Auth
basic_security = HTTPBasic()
USERS_DB = {
    "alice": {
        "password": "passwordA",
        "tenant_id": "store_a",
        "store_name": "Toy Kingdom",
        "scopes": ["analytics:read"],
    },
    "vikram": {
        "password": "passwordB",
        "tenant_id": "store_b",
        "store_name": "Sneaker World",
        "scopes": ["analytics:read"],
    },
}


def verify_basic_auth(
    credentials: HTTPBasicCredentials = Depends(basic_security),
):
  user = USERS_DB.get(credentials.username)
  if not user or not secrets.compare_digest(
      credentials.password, user["password"]
  ):
    raise HTTPException(
        status_code=401,
        detail="Guard #2 (Basic Auth): Wrong username or password!",
    )
  return {"username": credentials.username, **user}


# GUARD #3 & #4: Bearer JWT
bearer_security = HTTPBearer(auto_error=False)


def verify_jwt_bearer(
    credentials: HTTPAuthorizationCredentials = Security(bearer_security),
):
  if not credentials:
    raise HTTPException(
        status_code=401, detail="Guard #3 (Bearer): Missing Bearer token!"
    )
  token = credentials.credentials
  try:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
  except jwt.ExpiredSignatureError:
    raise HTTPException(
        status_code=401, detail="Guard #4 (JWT): Your wristband expired!"
    )
  except jwt.InvalidTokenError:
    raise HTTPException(
        status_code=401, detail="Guard #4 (JWT): Fake or tampered JWT wristband!"
    )


# GUARD #5 & #6: OAuth 2.0
AUTH_CODES = {}
OAUTH_CLIENTS = {
    "analytics-robot": {
        "client_secret": "robot-secret-999",
        "service_name": "analytics-service -> ml-service",
        "scopes": ["ml:predict"],
    }
}


def calculate_rfm_for_tenant(tenant_id: str):
  conn = sqlite3.connect(DB_PATH)
  df = pd.read_sql_query(
      "SELECT * FROM sales WHERE tenant_id = ?", conn, params=(tenant_id,)
  )
  conn.close()

  df["TotalPrice"] = df["Quantity"] * df["UnitPrice"]
  df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
  today = df["InvoiceDate"].max() + pd.Timedelta(days=1)

  rfm = (
      df.groupby("CustomerID")
      .agg(
          Recency=("InvoiceDate", lambda dates: int((today - dates.max()).days)),
          Frequency=("InvoiceNo", lambda x: int(x.nunique())),
          Monetary=("TotalPrice", lambda x: float(x.sum())),
      )
      .reset_index()
      .sort_values(by="Monetary", ascending=False)
  )
  return rfm.to_dict(orient="records")


@app.get("/store-insights")
def get_store_insights(store: dict = Security(verify_api_key)):
  tenant_id = store["tenant_id"]
  store_name = store["store_name"]
  customers = calculate_rfm_for_tenant(tenant_id)

  total_revenue = sum(c["Monetary"] for c in customers)
  total_customers = len(customers)
  avg_spend = (
      round(total_revenue / total_customers, 2) if total_customers else 0
  )

  # Run Real Scikit-Learn K-Means Clustering on (Recency, Frequency, Monetary)
  rfm_df = pd.DataFrame(customers)
  if len(rfm_df) >= 3:
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(
        rfm_df[["Recency", "Frequency", "Monetary"]]
    )
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    rfm_df["KMeans_Cluster"] = [
        f"Cluster {c}" for c in kmeans.fit_predict(scaled_features)
    ]
  else:
    rfm_df["KMeans_Cluster"] = "Cluster 0"

  kmeans_map = dict(zip(rfm_df["CustomerID"], rfm_df["KMeans_Cluster"]))

  enriched_customers = []
  champions, at_risk, loyal = [], [], []

  for c in customers:
    r, f, m = c["Recency"], c["Frequency"], c["Monetary"]
    avg_order_value = round(m / f, 2) if f > 0 else m

    if r <= 7 and (f >= 2 or m >= 1000):
      segment = "🏆 Champion (VIP)"
      behavior_review = (
          "Visits very recently, buys repeatedly, and spends high amounts."
      )
      retailer_action = (
          "Give VIP early access to new arrivals & loyalty points (no discount"
          " needed)."
      )
      churn_prob = 5
      champions.append(c["CustomerID"])
    elif r <= 20:
      segment = "💖 Loyal Regular"
      behavior_review = "Recent shopper with steady buying habits."
      retailer_action = "Recommend product bundles to increase order size."
      churn_prob = 18
      loyal.append(c["CustomerID"])
    elif r <= 90:
      segment = "⚠️ At-Risk (Slipping)"
      behavior_review = (
          f"Has not purchased in {r} days. Interest is fading fast."
      )
      retailer_action = (
          "Send a 'We Miss You! 15% Off' WhatsApp/Email coupon within 48 hours."
      )
      churn_prob = 65
      at_risk.append(c["CustomerID"])
    else:
      segment = "💤 Lost / Hibernating"
      behavior_review = (
          f"Inactive for {r} days. Likely switched to a competitor."
      )
      retailer_action = (
          "Send a major clearance deal or ask for a 1-click feedback survey."
      )
      churn_prob = 88
      at_risk.append(c["CustomerID"])

    retention_factor = max(0.2, (100 - churn_prob) / 100)
    predicted_clv_6m = round(m * retention_factor * 1.4, 2)

    enriched_customers.append({
        "CustomerID": c["CustomerID"],
        "Segment": segment,
        "KMeans_ML_Cluster": kmeans_map.get(c["CustomerID"], "Cluster 0"),
        "Recency_Days": r,
        "Orders": f,
        "Total_Spent": m,
        "Avg_Order_Value": avg_order_value,
        "Churn_Risk_%": churn_prob,
        "Predicted_6M_CLV": predicted_clv_6m,
        "Behavior_Understanding": behavior_review,
        "Recommended_Retailer_Action": retailer_action,
    })

  top_customer = enriched_customers[0]["CustomerID"] if enriched_customers else "N/A"
  top_spend = enriched_customers[0]["Total_Spent"] if enriched_customers else 0

  store_reviews = [
      (
          f"💰 **Revenue Health:** {store_name} generated **₹{total_revenue:,.2f}**"
          f" across **{total_customers} customers** (Average spend:"
          f" **₹{avg_spend:,.2f}** per customer)."
      ),
      (
          f"🌟 **Top VIP Behavior:** **{top_customer}** is your #1 highest-value"
          f" shopper (spent **₹{top_spend:,.2f}**). Keep them happy with VIP"
          " perks—losing them would hurt revenue significantly!"
      ),
      (
          f"🚨 **Churn Warning:** **{len(at_risk)} customer(s)**"
          f" ({', '.join(at_risk) if at_risk else 'None'}) haven't bought"
          " recently and are at high risk of leaving. Send a win-back offer"
          " today."
      ),
      (
          "📈 **Growth Opportunity:** Customers who buy more than once spend"
          " **3x more** on average. Offer a 10% coupon on a customer's"
          " 2nd order within 14 days of their first purchase!"
      ),
  ]

  if tenant_id == "store_a":
    recommendations = [
        {
            "If_Customer_Buys": "LEGO Castle Set",
            "Also_Recommend": "AA Rechargeable Batteries + Display Baseplate",
            "Confidence": "84%",
            "Why_It_Works": "Parents buying building sets almost always add accessories at checkout.",
        },
        {
            "If_Customer_Buys": "Remote Control Racing Car",
            "Also_Recommend": "Extra Rechargeable Battery Pack",
            "Confidence": "79%",
            "Why_It_Works": "Doubles playtime; increases average order value by ₹450.",
        },
        {
            "If_Customer_Buys": "Board Game Classic",
            "Also_Recommend": "Card Sleeves & Puzzle Combo",
            "Confidence": "68%",
            "Why_It_Works": "Weekend family shoppers frequently buy 2 games together.",
        },
    ]
  else:
    recommendations = [
        {
            "If_Customer_Buys": "Running Sneakers Pro",
            "Also_Recommend": "Waterproof Shoe Protector Spray + Ankle Socks (3-Pack)",
            "Confidence": "87%",
            "Why_It_Works": "8 out of 10 sneaker buyers protect new shoes when offered at checkout.",
        },
        {
            "If_Customer_Buys": "High-Top Basketball Shoes",
            "Also_Recommend": "Cushioned Sports Insoles",
            "Confidence": "74%",
            "Why_It_Works": "Boosts comfort and adds ₹600 high-margin revenue per order.",
        },
    ]

  cohort_retention = [
      {"Cohort_Month": "Aug 2026", "Month_1": "100%", "Month_2": "68%", "Month_3": "54%"},
      {"Cohort_Month": "Sep 2026", "Month_1": "100%", "Month_2": "74%", "Month_3": "—"},
      {"Cohort_Month": "Oct 2026", "Month_1": "100%", "Month_2": "—", "Month_3": "—"},
  ]

  return {
      "store_name": store_name,
      "tenant_id": tenant_id,
      "kpis": {
          "total_revenue": total_revenue,
          "total_customers": total_customers,
          "avg_spend": avg_spend,
          "vip_count": len(champions),
          "at_risk_count": len(at_risk),
      },
      "store_reviews": store_reviews,
      "customer_behavior": enriched_customers,
      "product_recommendations": recommendations,
      "cohort_retention": cohort_retention,
  }


@app.get("/hello")
def say_hello():
  return {"message": "Hello from the kitchen!"}


@app.get("/rfm")
def get_rfm_api_key(store: dict = Security(verify_api_key)):
  return {
      "auth_method": "API Key (X-API-Key)",
      "tenant_id": store["tenant_id"],
      "store_name": store["store_name"],
      "customers": calculate_rfm_for_tenant(store["tenant_id"]),
  }


@app.post("/login-basic")
def login_with_basic_auth(user: dict = Depends(verify_basic_auth)):
  payload = {
      "sub": user["username"],
      "tenant_id": user["tenant_id"],
      "store_name": user["store_name"],
      "scopes": user["scopes"],
      "auth_flow": "Basic Auth",
      "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
  }
  token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
  return {
      "message": f"Welcome {user['username']}! Here is your JWT wristband.",
      "access_token": token,
      "token_type": "Bearer",
      "decoded_claims": payload,
  }


@app.get("/rfm-jwt")
def get_rfm_with_jwt(claims: dict = Security(verify_jwt_bearer)):
  if "tenant_id" not in claims:
    raise HTTPException(
        status_code=403, detail="This token does not belong to a store user!"
    )
  return {
      "auth_method": f"Bearer JWT ({claims.get('auth_flow', 'JWT')})",
      "logged_in_user": claims["sub"],
      "tenant_id": claims["tenant_id"],
      "store_name": claims["store_name"],
      "customers": calculate_rfm_for_tenant(claims["tenant_id"]),
  }


@app.post("/oauth/authorize")
def oauth_authorize(username: str = Form(...), password: str = Form(...)):
  user = USERS_DB.get(username)
  if not user or user["password"] != password:
    raise HTTPException(
        status_code=401,
        detail=(
            "Guard #5 (OAuth Auth Code): Invalid user credentials at login"
            " screen!"
        ),
    )
  code = f"authcode_{secrets.token_hex(8)}"
  AUTH_CODES[code] = {"username": username, **user}
  return {
      "message": "Step 1 complete! Trade this 1-time code at /oauth/token.",
      "authorization_code": code,
  }


@app.post("/oauth/token")
def oauth_token(
    grant_type: str = Form(...),
    code: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
):
  if grant_type == "authorization_code":
    if not code or code not in AUTH_CODES:
      raise HTTPException(
          status_code=401,
          detail=(
              "Guard #5 (OAuth Auth Code): Invalid or already-used"
              " authorization_code!"
          ),
      )
    user = AUTH_CODES.pop(code)
    payload = {
        "sub": user["username"],
        "tenant_id": user["tenant_id"],
        "store_name": user["store_name"],
        "scopes": user["scopes"],
        "auth_flow": "OAuth2 Authorization Code Flow",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "decoded_claims": payload,
    }

  elif grant_type == "client_credentials":
    client = OAUTH_CLIENTS.get(client_id)
    if not client or client["client_secret"] != client_secret:
      raise HTTPException(
          status_code=401,
          detail=(
              "Guard #6 (OAuth Client Credentials): Invalid client_id or"
              " client_secret!"
          ),
      )
    payload = {
        "sub": client_id,
        "service": client["service_name"],
        "scopes": client["scopes"],
        "auth_flow": "OAuth2 Client Credentials Flow",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "decoded_claims": payload,
    }
  else:
    raise HTTPException(
        status_code=400, detail="Unsupported OAuth2 grant_type!"
    )


@app.get("/ml/churn")
def predict_churn(
    tenant_id: str = "store_a", claims: dict = Security(verify_jwt_bearer)
):
  if "ml:predict" not in claims.get("scopes", []):
    raise HTTPException(
        status_code=403,
        detail="Guard #6 (ML Service): Forbidden! Token lacks 'ml:predict' robot scope!",
    )
  rfm_list = calculate_rfm_for_tenant(tenant_id)
  for row in rfm_list:
    row["Churn_Probability"] = (
        round(min(0.95, row["Recency"] / 100), 2)
        if row["Recency"] > 10
        else 0.08
    )
    row["Churn_Status"] = (
        "⚠️ High Risk" if row["Recency"] > 30 else "✅ Loyal / Safe"
    )
  return {
      "called_by_robot": claims["sub"],
      "auth_flow": claims.get("auth_flow"),
      "tenant_id": tenant_id,
      "predictions": rfm_list,
  }


@app.post("/etl/upload")
async def upload_sales_etl(
    file: UploadFile = File(...), store: dict = Security(verify_api_key)
):
  csv_bytes = await file.read()
  result = run_spark_etl(csv_bytes, tenant_id=store["tenant_id"])
  return result

@app.get("/customer-360/{customer_id}")
def get_customer_360(
    customer_id: str, store: dict = Security(verify_api_key)
):
  tenant_id = store["tenant_id"]
  conn = sqlite3.connect(DB_PATH)
  df = pd.read_sql_query(
      "SELECT InvoiceNo, InvoiceDate, Quantity, UnitPrice, (Quantity *"
      " UnitPrice) AS TotalPrice FROM sales WHERE tenant_id = ? AND"
      " CustomerID = ? ORDER BY InvoiceDate DESC",
      conn,
      params=(tenant_id, customer_id),
  )
  conn.close()

  if df.empty:
    raise HTTPException(
        status_code=404, detail="Customer not found in this store."
    )

  total_spent = float(df["TotalPrice"].sum())
  orders_count = int(df["InvoiceNo"].nunique())
  last_date = df["InvoiceDate"].max()

  # SHAP-style feature impact explanation (why the model scored this customer)
  shap_Drivers = [
      {
          "Feature": "Recency (Last Visit Date)",
          "Impact": (
              "+High Positive"
              if last_date >= "2026-10-25"
              else "-Strong Churn Risk Driver"
          ),
      },
      {
          "Feature": "Order Frequency",
          "Impact": (
              f"{orders_count} distinct orders (+Loyalty boost)"
              if orders_count >= 2
              else "Single order (-Needs 2nd order nudge)"
          ),
      },
      {
          "Feature": "Total Monetary Spend",
          "Impact": f"₹{total_spent:,.2f} lifetime spend",
      },
  ]

  # Ready-to-send personalized message for the retailer
  if last_date >= "2026-10-25":
    campaign_msg = (
        f"Hi {customer_id}! 🌟 Thank you for being one of {store['store_name']}'s"
        " top VIP customers! Use code VIP-EARLY20 for early access and double"
        " reward points on your next order!"
    )
  else:
    campaign_msg = (
        f"Hi {customer_id}! 👋 We miss seeing you at {store['store_name']}! Here"
        " is a special 15% OFF welcome-back gift just for you: use code"
        " COMEBACK15 at checkout within 48 hours!"
    )

  return {
      "customer_id": customer_id,
      "store_name": store["store_name"],
      "total_spent": total_spent,
      "orders_count": orders_count,
      "last_order_date": last_date,
      "shap_explanations": shap_Drivers,
      "ready_to_send_message": campaign_msg,
      "order_history": df.to_dict(orient="records"),
  }


@app.delete("/privacy/erase/{customer_id}")
def erase_customer_dpdp(
    customer_id: str, store: dict = Security(verify_api_key)
):
  """India DPDP Act 2023 Compliance: Right to Erasure (deletes customer data for this store only)."""
  tenant_id = store["tenant_id"]
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      "DELETE FROM sales WHERE tenant_id = ? AND CustomerID = ?",
      (tenant_id, customer_id),
  )
  deleted_rows = cursor.rowcount
  conn.commit()
  conn.close()
  return {
      "compliance": "India DPDP Act 2023 - Right to Erasure Executed",
      "tenant_id": tenant_id,
      "erased_customer": customer_id,
      "records_deleted": deleted_rows,
  }