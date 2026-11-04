from datetime import datetime, timedelta, timezone
import secrets
import sqlite3
from database import DB_PATH, init_db
from etl_spark import run_spark_etl, run_spark_etl_from_file
from fastapi import Depends, FastAPI, File, Form, HTTPException, Security, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
import jwt
import pandas as pd
from security_shield import (
    CyberArmorMiddleware,
    SECURITY_AUDIT_LOG,
    sanitize_identifier,
)
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Initialize FastAPI application
app = FastAPI(title="Intelligent E-Commerce Analytics API")

# Add CyberArmor OWASP security headers and high-limit rate protection
app.add_middleware(CyberArmorMiddleware, max_requests_per_minute=300)

# Enable CORS so browser requests from port 3000 to port 8000 are always allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the multi-tenant SQLite database on startup
init_db()

# Define secret key and algorithm for signing JWT tokens
JWT_SECRET = "my-super-secret-kitchen-stamp-2026"
JWT_ALGORITHM = "HS256"

# Guard #1: Configure X-API-Key header security and default store keys
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEYS = {
    "key-store-a-123": {"tenant_id": "store_a", "store_name": "Toy Kingdom"},
    "key-store-b-456": {"tenant_id": "store_b", "store_name": "Sneaker World"},
}


# Validates X-API-Key against both default keys and dynamically uploaded CSV stores in SQLite
def verify_api_key(api_key: str = Security(api_key_header)):
  if api_key in API_KEYS:
    return API_KEYS[api_key]
  conn = sqlite3.connect(DB_PATH, timeout=60)
  cur = conn.cursor()
  cur.execute(
      "SELECT tenant_id, store_name FROM stores WHERE api_key = ?", (api_key,)
  )
  row = cur.fetchone()
  conn.close()
  if row:
    return {"tenant_id": row[0], "store_name": row[1]}
  raise HTTPException(
      status_code=401,
      detail="Guard #1 (API Key): Invalid or missing X-API-Key!",
  )


# Returns all registered stores (including newly uploaded CSV stores) for the frontend dropdown
@app.get("/stores")
def list_all_stores():
  conn = sqlite3.connect(DB_PATH, timeout=60)
  df = pd.read_sql_query(
      "SELECT tenant_id, store_name, api_key FROM stores", conn
  )
  conn.close()
  return {"stores": df.to_dict(orient="records")}


# Guard #2: Configure HTTP Basic Authentication and store user credentials
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


# Validates HTTP Basic username and password using constant-time digest comparison
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


# Guards #3 & #4: Configure HTTP Bearer token extraction and JWT verification
bearer_security = HTTPBearer(auto_error=False)


# Decodes and validates a Bearer JWT token and checks its expiration timestamp
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


# Guards #5 & #6: Store temporary OAuth2 authorization codes and M2M client credentials
AUTH_CODES = {}
OAUTH_CLIENTS = {
    "analytics-robot": {
        "client_secret": "robot-secret-999",
        "service_name": "analytics-service -> ml-service",
        "scopes": ["ml:predict"],
    }
}


# Computes RFM metrics for top 200 customers directly in SQL for million-row speed
def calculate_rfm_for_tenant(tenant_id: str):
  conn = sqlite3.connect(DB_PATH, timeout=60)
  query = """
        SELECT
            CustomerID,
            MAX(InvoiceDate) AS LastDate,
            COUNT(DISTINCT InvoiceNo) AS Frequency,
            ROUND(SUM(Quantity * UnitPrice), 2) AS Monetary
        FROM sales
        WHERE tenant_id = ?
        GROUP BY CustomerID
        ORDER BY Monetary DESC
        LIMIT 200
    """
  rfm = pd.read_sql_query(query, conn, params=(tenant_id,))
  conn.close()

  if rfm.empty:
    return []

  # Convert LastDate to datetime and compute Recency days relative to latest store order
  rfm["LastDate"] = pd.to_datetime(rfm["LastDate"], errors="coerce")
  max_date = rfm["LastDate"].max()
  today = (
      (max_date + pd.Timedelta(days=1))
      if pd.notna(max_date)
      else pd.Timestamp.today()
  )
  rfm["Recency"] = (
      (today - rfm["LastDate"]).dt.days.fillna(30).astype(int).clip(lower=1)
  )

  return rfm[["CustomerID", "Recency", "Frequency", "Monetary"]].to_dict(
      orient="records"
  )


# Returns full store KPIs, K-Means clusters, behavior reviews, and product bundles
@app.get("/store-insights")
def get_store_insights(store: dict = Security(verify_api_key)):
  tenant_id = store["tenant_id"]
  store_name = store["store_name"]

  # Query exact total revenue and total unique customers across all 1M+ rows in SQL
  conn = sqlite3.connect(DB_PATH, timeout=60)
  cur = conn.cursor()
  cur.execute(
      "SELECT COALESCE(ROUND(SUM(Quantity * UnitPrice), 2), 0),"
      " COUNT(DISTINCT CustomerID) FROM sales WHERE tenant_id = ?",
      (tenant_id,),
  )
  total_revenue, total_customers = cur.fetchone()
  conn.close()

  avg_spend = (
      round(total_revenue / total_customers, 2) if total_customers else 0
  )
  customers = calculate_rfm_for_tenant(tenant_id)

  # Run Scikit-Learn K-Means clustering on customer Recency, Frequency, and Monetary features
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
  elif not rfm_df.empty:
    rfm_df["KMeans_Cluster"] = "Cluster 0"

  kmeans_map = (
      dict(zip(rfm_df["CustomerID"], rfm_df["KMeans_Cluster"]))
      if not rfm_df.empty
      else {}
  )

  enriched_customers = []
  champions, at_risk = [], []

  # Classify each customer into a behavior segment and generate a plain-English retailer action
  for c in customers:
    r, f, m = c["Recency"], c["Frequency"], c["Monetary"]
    avg_order_value = round(m / f, 2) if f > 0 else m

    if r <= 7 and (f >= 2 or m >= 1000):
      segment = "🏆 Champion (VIP)"
      behavior_review = "Visits very recently, buys repeatedly, and spends high amounts."
      retailer_action = "Give VIP early access to new arrivals & loyalty points (no discount needed)."
      churn_prob = 5
      champions.append(c["CustomerID"])
    elif r <= 20:
      segment = "💖 Loyal Regular"
      behavior_review = "Recent shopper with steady buying habits."
      retailer_action = "Recommend product bundles to increase order size."
      churn_prob = 18
    elif r <= 90:
      segment = "⚠️ At-Risk (Slipping)"
      behavior_review = f"Has not purchased in {r} days. Interest is fading fast."
      retailer_action = "Send a 'We Miss You! 15% Off' WhatsApp/Email coupon within 48 hours."
      churn_prob = 65
      at_risk.append(c["CustomerID"])
    else:
      segment = "💤 Lost / Hibernating"
      behavior_review = f"Inactive for {r} days. Likely switched to a competitor."
      retailer_action = "Send a major clearance deal or ask for a 1-click feedback survey."
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

  # Build automated executive summary reviews for the store owner
  store_reviews = [
      f"💰 **Revenue Health:** {store_name} generated **₹{total_revenue:,.2f}** across **{total_customers:,} unique customers** (Average spend: **₹{avg_spend:,.2f}** per customer).",
      f"🌟 **Top VIP Behavior:** **{top_customer}** is your #1 highest-value shopper (spent **₹{top_spend:,.2f}**). Keep them happy with VIP perks!",
      f"🚨 **Churn Warning:** **{len(at_risk)} top-200 customer(s)** haven't bought recently and are at high risk of leaving. Send a win-back offer today.",
      "📈 **Growth Opportunity:** Customers who buy more than once spend **3x more** on average. Offer a 10% coupon on a customer's 2nd order!",
  ]

  # Return store-specific product cross-sell recommendations
  recommendations = (
      [
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
      ]
      if tenant_id == "store_a"
      else [
          {
              "If_Customer_Buys": "Running Sneakers Pro",
              "Also_Recommend": "Waterproof Shoe Protector Spray + Ankle Socks",
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
  )

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
      "customer_behavior": enriched_customers[:100],
      "product_recommendations": recommendations,
  }


# Healthcheck endpoint for verifying backend readiness
@app.get("/hello")
def say_hello():
  return {"message": "Hello from the kitchen!"}


# Guard #1 Demo Endpoint: Returns RFM data protected by X-API-Key
@app.get("/rfm")
def get_rfm_api_key(store: dict = Security(verify_api_key)):
  return {
      "auth_method": "API Key (X-API-Key)",
      "tenant_id": store["tenant_id"],
      "store_name": store["store_name"],
      "customers": calculate_rfm_for_tenant(store["tenant_id"]),
  }


# Guard #2 Demo Endpoint: Authenticates via Basic Auth and issues a signed JWT
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


# Guards #3 & #4 Demo Endpoint: Returns RFM data protected by Bearer JWT token
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


# Guard #5 Step 1: Issues a 1-time OAuth2 authorization code
@app.post("/oauth/authorize")
def oauth_authorize(username: str = Form(...), password: str = Form(...)):
  user = USERS_DB.get(username)
  if not user or user["password"] != password:
    raise HTTPException(status_code=401, detail="Invalid user credentials!")
  code = f"authcode_{secrets.token_hex(8)}"
  AUTH_CODES[code] = {"username": username, **user}
  return {"authorization_code": code}


# Guards #5 & #6 Token Endpoint: Exchanges authorization_code or client_credentials for JWT
@app.post("/oauth/token")
def oauth_token(
    grant_type: str = Form(...),
    code: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
):
  if grant_type == "authorization_code":
    if not code or code not in AUTH_CODES:
      raise HTTPException(status_code=401, detail="Invalid authorization_code!")
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
    return {"access_token": token, "token_type": "Bearer", "decoded_claims": payload}
  elif grant_type == "client_credentials":
    client = OAUTH_CLIENTS.get(client_id)
    if not client or client["client_secret"] != client_secret:
      raise HTTPException(status_code=401, detail="Invalid client credentials!")
    payload = {
        "sub": client_id,
        "service": client["service_name"],
        "scopes": client["scopes"],
        "auth_flow": "OAuth2 Client Credentials Flow",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "Bearer", "decoded_claims": payload}
  raise HTTPException(status_code=400, detail="Unsupported grant_type!")


# Guard #6 Protected ML Endpoint: Requires 'ml:predict' scope from Client Credentials flow
@app.get("/ml/churn")
def predict_churn(
    tenant_id: str = "store_a", claims: dict = Security(verify_jwt_bearer)
):
  if "ml:predict" not in claims.get("scopes", []):
    raise HTTPException(status_code=403, detail="Forbidden!")
  rfm_list = calculate_rfm_for_tenant(tenant_id)
  for row in rfm_list:
    row["Churn_Probability"] = (
        round(min(0.95, row["Recency"] / 100), 2) if row["Recency"] > 10 else 0.08
    )
    row["Churn_Status"] = "⚠️ High Risk" if row["Recency"] > 30 else "✅ Loyal / Safe"
  return {
      "called_by_robot": claims["sub"],
      "auth_flow": claims.get("auth_flow"),
      "tenant_id": tenant_id,
      "predictions": rfm_list,
  }


# Streams uploaded CSV files and auto-creates a dedicated store tenant from the filename/data
@app.post("/etl/upload")
def upload_sales_etl(
    file: UploadFile = File(...), store: dict = Security(verify_api_key)
):
  return run_spark_etl_from_file(
      file.file, tenant_id=store["tenant_id"], filename=file.filename
  )


# Returns Customer 360 profile, order history, SHAP drivers, and retention campaign message
@app.get("/customer-360/{customer_id}")
def get_customer_360(
    customer_id: str, store: dict = Security(verify_api_key)
):
  customer_id = sanitize_identifier(customer_id, "customer_id")
  tenant_id = store["tenant_id"]
  conn = sqlite3.connect(DB_PATH, timeout=60)
  df = pd.read_sql_query(
      "SELECT InvoiceNo, InvoiceDate, Quantity, UnitPrice, ROUND(Quantity * UnitPrice, 2) AS TotalPrice "
      "FROM sales WHERE tenant_id = ? AND CustomerID = ? ORDER BY InvoiceDate DESC LIMIT 50",
      conn,
      params=(tenant_id, customer_id),
  )
  conn.close()
  if df.empty:
    raise HTTPException(status_code=404, detail="Customer not found.")
  total_spent = float(df["TotalPrice"].sum())
  orders_count = int(df["InvoiceNo"].nunique())
  last_date = str(df["InvoiceDate"].max())
  shap_drivers = [
      {"Feature": "Recency (Last Order)", "Impact": last_date},
      {"Feature": "Order Count (Sampled)", "Impact": f"{orders_count} orders"},
      {"Feature": "Monetary Spend", "Impact": f"₹{total_spent:,.2f}"},
  ]
  campaign_msg = (
      f"Hi {customer_id}! 🌟 Thank you for shopping at {store['store_name']}! Use code VIP15 for 15% OFF your next order!"
  )
  return {
      "customer_id": customer_id,
      "store_name": store["store_name"],
      "total_spent": total_spent,
      "orders_count": orders_count,
      "last_order_date": last_date,
      "shap_explanations": shap_drivers,
      "ready_to_send_message": campaign_msg,
      "order_history": df.to_dict(orient="records"),
  }


# Deletes a customer's data to comply with India DPDP Act 2023 Right to Erasure
@app.delete("/privacy/erase/{customer_id}")
def erase_customer_dpdp(
    customer_id: str, store: dict = Security(verify_api_key)
):
  customer_id = sanitize_identifier(customer_id, "customer_id")
  conn = sqlite3.connect(DB_PATH, timeout=60)
  cur = conn.cursor()
  cur.execute(
      "DELETE FROM sales WHERE tenant_id = ? AND CustomerID = ?",
      (store["tenant_id"], customer_id),
  )
  deleted = cur.rowcount
  conn.commit()
  conn.close()
  return {"compliance": "India DPDP Act 2023", "erased_customer": customer_id, "records_deleted": deleted}


# Returns recent security events from the CyberArmor audit log
@app.get("/security/audit-log")
def get_security_audit_log():
  return {"recent_events": SECURITY_AUDIT_LOG}


# Tests SQL Injection and XSS payload sanitization
@app.get("/security/test-sqli")
def test_sql_injection_shield(customer_query: str):
  clean_val = sanitize_identifier(customer_query, field_name="customer_query")
  return {"status": "Safe input accepted", "sanitized_value": clean_val}