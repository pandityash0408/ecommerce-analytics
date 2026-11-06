from datetime import datetime, timedelta, timezone
import secrets
import sqlite3
from database import DB_PATH, init_db
from etl_spark import run_spark_etl, run_spark_etl_from_file
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Security, UploadFile
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
app = FastAPI(title="Enterprise E-Commerce Customer & Product Analytics API")

# Add CyberArmor OWASP security headers and rate limiting middleware
app.add_middleware(CyberArmorMiddleware, max_requests_per_minute=300)

# Enable CORS so browser requests from port 3000 to port 8000 are permitted
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables and indexes on startup
init_db()

JWT_SECRET = "my-super-secret-kitchen-stamp-2026"
JWT_ALGORITHM = "HS256"

# Guard #1: Configure X-API-Key header validation
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEYS = {
    "key-store-a-123": {"tenant_id": "store_a", "store_name": "Toy Kingdom"},
    "key-store-b-456": {"tenant_id": "store_b", "store_name": "Sneaker World"},
    "key-sample-sales": {"tenant_id": "dataset_sample_sales", "store_name": "sample_sales.csv"},
}


# Validates X-API-Key against registered datasets in SQLite or falls back to the most recent dataset
def verify_api_key(api_key: str = Security(api_key_header)):
  conn = sqlite3.connect(DB_PATH, timeout=60)
  cur = conn.cursor()
  if api_key:
    cur.execute("SELECT tenant_id, store_name FROM stores WHERE api_key = ?", (api_key,))
    row = cur.fetchone()
    if row:
      conn.close()
      return {"tenant_id": row[0], "store_name": row[1]}
    if api_key in API_KEYS:
      conn.close()
      return API_KEYS[api_key]
  conn.close()
  raise HTTPException(status_code=401, detail="Guard #1 (API Key): Invalid or missing X-API-Key!")


# Returns all uploaded datasets ordered from newest to oldest so the latest dataset loads automatically
@app.get("/stores")
def list_all_stores():
  conn = sqlite3.connect(DB_PATH, timeout=60)
  df = pd.read_sql_query(
      "SELECT tenant_id, store_name, api_key, created_at FROM stores ORDER BY created_at DESC",
      conn,
  )
  conn.close()
  return {"stores": df.to_dict(orient="records")}


# Guard #2: HTTP Basic Authentication configuration
basic_security = HTTPBasic()
USERS_DB = {
    "alice": {"password": "passwordA", "tenant_id": "store_a", "store_name": "Toy Kingdom", "scopes": ["analytics:read"]},
    "vikram": {"password": "passwordB", "tenant_id": "store_b", "store_name": "Sneaker World", "scopes": ["analytics:read"]},
}


def verify_basic_auth(credentials: HTTPBasicCredentials = Depends(basic_security)):
  user = USERS_DB.get(credentials.username)
  if not user or not secrets.compare_digest(credentials.password, user["password"]):
    raise HTTPException(status_code=401, detail="Guard #2 (Basic Auth): Wrong username or password!")
  return {"username": credentials.username, **user}


# Guards #3 & #4: HTTP Bearer JWT validation
bearer_security = HTTPBearer(auto_error=False)


def verify_jwt_bearer(credentials: HTTPAuthorizationCredentials = Security(bearer_security)):
  if not credentials:
    raise HTTPException(status_code=401, detail="Guard #3 (Bearer): Missing Bearer token!")
  try:
    return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
  except jwt.ExpiredSignatureError:
    raise HTTPException(status_code=401, detail="Guard #4 (JWT): Token expired!")
  except jwt.InvalidTokenError:
    raise HTTPException(status_code=401, detail="Guard #4 (JWT): Invalid token!")


AUTH_CODES = {}
OAUTH_CLIENTS = {
    "analytics-robot": {"client_secret": "robot-secret-999", "service_name": "analytics-service -> ml-service", "scopes": ["ml:predict"]}
}


# Computes RFM and total products dealt with for the top 200 customers in SQL
def calculate_rfm_for_tenant(tenant_id: str):
  conn = sqlite3.connect(DB_PATH, timeout=60)
  query = """
        SELECT
            CustomerID,
            MAX(InvoiceDate) AS LastDate,
            COUNT(DISTINCT InvoiceNo) AS Frequency,
            SUM(Quantity) AS TotalProducts,
            ROUND(SUM(Quantity * UnitPrice), 2) AS Monetary
        FROM sales
        WHERE tenant_id = ?
        GROUP BY CustomerID
        ORDER BY Monetary DESC, TotalProducts DESC
        LIMIT 200
    """
  rfm = pd.read_sql_query(query, conn, params=(tenant_id,))
  conn.close()

  if rfm.empty:
    return []

  rfm["LastDate"] = pd.to_datetime(rfm["LastDate"], errors="coerce")
  max_date = rfm["LastDate"].max()
  today = (max_date + pd.Timedelta(days=1)) if pd.notna(max_date) else pd.Timestamp.today()
  rfm["Recency"] = (today - rfm["LastDate"]).dt.days.fillna(30).astype(int).clip(lower=1)

  return rfm[["CustomerID", "Recency", "Frequency", "TotalProducts", "Monetary"]].to_dict(orient="records")


# Returns dataset KPIs including Best Customer, Worst Customer, K-Means segments, and executive reviews
@app.get("/store-insights")
def get_store_insights(store: dict = Security(verify_api_key)):
  tenant_id = store["tenant_id"]
  store_name = store["store_name"]

  conn = sqlite3.connect(DB_PATH, timeout=60)
  cur = conn.cursor()

  # 1. Query overall dataset revenue and customer count
  cur.execute(
      "SELECT COALESCE(ROUND(SUM(Quantity * UnitPrice), 2), 0), COUNT(DISTINCT CustomerID) FROM sales WHERE tenant_id = ?",
      (tenant_id,),
  )
  total_revenue, total_customers = cur.fetchone()

  # 2. Query Best Customer (highest spend + most products dealt with)
  cur.execute(
      """
      SELECT CustomerID, ROUND(SUM(Quantity * UnitPrice), 2) AS Spend, SUM(Quantity) AS Units
      FROM sales WHERE tenant_id = ?
      GROUP BY CustomerID
      ORDER BY Spend DESC, Units DESC LIMIT 1
      """,
      (tenant_id,),
  )
  best_row = cur.fetchone()
  best_customer = (
      {"id": best_row[0], "spend": best_row[1], "units": int(best_row[2])}
      if best_row
      else {"id": "N/A", "spend": 0, "units": 0}
  )

  # 3. Query Worst Customer (lowest spend + fewest products dealt with)
  cur.execute(
      """
      SELECT CustomerID, ROUND(SUM(Quantity * UnitPrice), 2) AS Spend, SUM(Quantity) AS Units
      FROM sales WHERE tenant_id = ?
      GROUP BY CustomerID
      ORDER BY Spend ASC, Units ASC LIMIT 1
      """,
      (tenant_id,),
  )
  worst_row = cur.fetchone()
  worst_customer = (
      {"id": worst_row[0], "spend": worst_row[1], "units": int(worst_row[2])}
      if worst_row
      else {"id": "N/A", "spend": 0, "units": 0}
  )
  conn.close()

  avg_spend = round(total_revenue / total_customers, 2) if total_customers else 0
  customers = calculate_rfm_for_tenant(tenant_id)

  # Run Scikit-Learn K-Means clustering on customer Recency, Frequency, and Monetary features
  rfm_df = pd.DataFrame(customers)
  if len(rfm_df) >= 3:
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(rfm_df[["Recency", "Frequency", "Monetary"]])
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    rfm_df["KMeans_Cluster"] = [f"Cluster {c}" for c in kmeans.fit_predict(scaled_features)]
  elif not rfm_df.empty:
    rfm_df["KMeans_Cluster"] = "Cluster 0"

  kmeans_map = dict(zip(rfm_df["CustomerID"], rfm_df["KMeans_Cluster"])) if not rfm_df.empty else {}

  enriched_customers = []
  at_risk = []

  for c in customers:
    r, f, m = c["Recency"], c["Frequency"], c["Monetary"]
    units = int(c.get("TotalProducts", f))
    avg_order_value = round(m / f, 2) if f > 0 else m

    if r <= 7 and (f >= 2 or m >= 1000):
      segment = "Champion (VIP)"
      behavior_review = "High-frequency buyer with recent activity and strong spend."
      retailer_action = "Provide priority account tier and early product access."
      churn_prob = 5
    elif r <= 20:
      segment = "Loyal Regular"
      behavior_review = "Consistent repeat buyer with stable order volume."
      retailer_action = "Introduce volume tier discounts to increase order size."
      churn_prob = 18
    elif r <= 90:
      segment = "At-Risk (Slipping)"
      behavior_review = f"No purchase recorded for {r} days; engagement declining."
      retailer_action = "Send targeted 15% retention incentive within 48 hours."
      churn_prob = 65
      at_risk.append(c["CustomerID"])
    else:
      segment = "Lost / Inactive"
      behavior_review = f"Inactive for {r} days; high probability of churn."
      retailer_action = "Trigger win-back campaign or account check-in survey."
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
        "Total_Products": units,
        "Total_Spent": m,
        "Avg_Order_Value": avg_order_value,
        "Churn_Risk_%": churn_prob,
        "Predicted_6M_CLV": predicted_clv_6m,
        "Behavior_Understanding": behavior_review,
        "Recommended_Retailer_Action": retailer_action,
    })

  store_reviews = [
      f"**Revenue Summary:** Dataset **{store_name}** recorded **₹{total_revenue:,.2f}** across **{total_customers:,} customers** (Average spend: **₹{avg_spend:,.2f}**).",
      f"**Best Customer Performance:** **{best_customer['id']}** leads with **₹{best_customer['spend']:,.2f}** total spend across **{best_customer['units']:,} units**.",
      f"**Lowest Customer Activity:** **{worst_customer['id']}** recorded the lowest activity with **₹{worst_customer['spend']:,.2f}** across **{worst_customer['units']:,} unit(s)**.",
      f"**Retention Risk:** **{len(at_risk)} customer(s)** in the top cohort show elevated churn risk and require follow-up.",
  ]

  return {
      "store_name": store_name,
      "tenant_id": tenant_id,
      "kpis": {
          "total_revenue": total_revenue,
          "total_customers": total_customers,
          "avg_spend": avg_spend,
          "best_customer": best_customer,
          "worst_customer": worst_customer,
      },
      "store_reviews": store_reviews,
      "customer_behavior": enriched_customers[:100],
  }


# Searches distinct products in the active dataset by keyword and returns top matching products
@app.get("/products/search")
def search_products(q: str = "", store: dict = Security(verify_api_key)):
  tenant_id = store["tenant_id"]
  conn = sqlite3.connect(DB_PATH, timeout=60)
  if q.strip():
    df = pd.read_sql_query(
        """
        SELECT Product, SUM(Quantity) AS TotalUnits, ROUND(SUM(Quantity * UnitPrice), 2) AS TotalRevenue
        FROM sales
        WHERE tenant_id = ? AND Product LIKE ?
        GROUP BY Product
        ORDER BY TotalRevenue DESC
        LIMIT 30
        """,
        conn,
        params=(tenant_id, f"%{q.strip()}%"),
    )
  else:
    df = pd.read_sql_query(
        """
        SELECT Product, SUM(Quantity) AS TotalUnits, ROUND(SUM(Quantity * UnitPrice), 2) AS TotalRevenue
        FROM sales
        WHERE tenant_id = ?
        GROUP BY Product
        ORDER BY TotalRevenue DESC
        LIMIT 30
        """,
        conn,
        params=(tenant_id,),
    )
  conn.close()
  return {"products": df.to_dict(orient="records")}


# Returns Year-wise (YYYY) or Month-wise (YYYY-MM) sales trends for one or multiple selected products
# Returns Year-wise (YYYY) or Month-wise (YYYY-MM) sales trends for one or multiple selected products
@app.get("/products/trends")
def get_product_trends(
    granularity: str = "month",
    products: list[str] = Query(default=[]),
    store: dict = Security(verify_api_key),
):
  tenant_id = store["tenant_id"]
  date_len = 4 if granularity == "year" else 7

  # Split any comma-separated product strings back into distinct product names
  clean_products = []
  for p in products:
    for item in p.split(","):
      if item.strip() and item.strip() not in clean_products:
        clean_products.append(item.strip())
  products = clean_products

  conn = sqlite3.connect(DB_PATH, timeout=60)
  # If no products are selected, automatically pick the top 3 products by revenue
  if not products:
    top_df = pd.read_sql_query(
        "SELECT Product FROM sales WHERE tenant_id = ? GROUP BY Product ORDER BY SUM(Quantity * UnitPrice) DESC LIMIT 3",
        conn,
        params=(tenant_id,),
    )
    products = top_df["Product"].tolist()

  if not products:
    conn.close()
    return {"periods": [], "series": [], "selected_products": []}

  placeholders = ",".join(["?"] * len(products))
  query = f"""
        SELECT
            SUBSTR(InvoiceDate, 1, {date_len}) AS Period,
            Product,
            ROUND(SUM(Quantity * UnitPrice), 2) AS Revenue,
            SUM(Quantity) AS Units
        FROM sales
        WHERE tenant_id = ? AND Product IN ({placeholders})
        GROUP BY Period, Product
        ORDER BY Period ASC
    """
  df = pd.read_sql_query(query, conn, params=[tenant_id] + list(products))
  conn.close()

  periods = sorted(df["Period"].dropna().unique().tolist())
  series = []
  for prod in products:
    prod_df = df[df["Product"] == prod].set_index("Period")
    series.append({
        "product": prod,
        "revenue": [float(prod_df.loc[p, "Revenue"]) if p in prod_df.index else 0.0 for p in periods],
        "units": [int(prod_df.loc[p, "Units"]) if p in prod_df.index else 0 for p in periods],
    })

  return {"granularity": granularity, "periods": periods, "series": series, "selected_products": products}


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
  return {"message": f"Welcome {user['username']}!", "access_token": token, "token_type": "Bearer", "decoded_claims": payload}


@app.get("/rfm-jwt")
def get_rfm_with_jwt(claims: dict = Security(verify_jwt_bearer)):
  if "tenant_id" not in claims:
    raise HTTPException(status_code=403, detail="Token lacks tenant_id!")
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
    raise HTTPException(status_code=401, detail="Invalid credentials!")
  code = f"authcode_{secrets.token_hex(8)}"
  AUTH_CODES[code] = {"username": username, **user}
  return {"authorization_code": code}


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


@app.get("/ml/churn")
def predict_churn(tenant_id: str = "store_a", claims: dict = Security(verify_jwt_bearer)):
  if "ml:predict" not in claims.get("scopes", []):
    raise HTTPException(status_code=403, detail="Forbidden!")
  rfm_list = calculate_rfm_for_tenant(tenant_id)
  for row in rfm_list:
    row["Churn_Probability"] = round(min(0.95, row["Recency"] / 100), 2) if row["Recency"] > 10 else 0.08
    row["Churn_Status"] = "High Risk" if row["Recency"] > 30 else "Loyal / Safe"
  return {"called_by_robot": claims["sub"], "auth_flow": claims.get("auth_flow"), "tenant_id": tenant_id, "predictions": rfm_list}


@app.post("/etl/upload")
def upload_sales_etl(file: UploadFile = File(...), store: dict = Security(verify_api_key)):
  return run_spark_etl_from_file(file.file, tenant_id=store["tenant_id"], filename=file.filename)


@app.get("/customer-360/{customer_id}")
def get_customer_360(customer_id: str, store: dict = Security(verify_api_key)):
  customer_id = sanitize_identifier(customer_id, "customer_id")
  tenant_id = store["tenant_id"]
  conn = sqlite3.connect(DB_PATH, timeout=60)
  df = pd.read_sql_query(
      "SELECT InvoiceNo, InvoiceDate, Product, Quantity, UnitPrice, ROUND(Quantity * UnitPrice, 2) AS TotalPrice "
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
      {"Feature": "Last Purchase Date", "Impact": last_date},
      {"Feature": "Distinct Orders", "Impact": f"{orders_count} orders"},
      {"Feature": "Sampled Spend", "Impact": f"₹{total_spent:,.2f}"},
  ]
  campaign_msg = f"Dear {customer_id}, thank you for your business with {store['store_name']}. Use code PARTNER15 for a 15% discount on your next order."
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


@app.delete("/privacy/erase/{customer_id}")
def erase_customer_dpdp(customer_id: str, store: dict = Security(verify_api_key)):
  customer_id = sanitize_identifier(customer_id, "customer_id")
  conn = sqlite3.connect(DB_PATH, timeout=60)
  cur = conn.cursor()
  cur.execute("DELETE FROM sales WHERE tenant_id = ? AND CustomerID = ?", (store["tenant_id"], customer_id))
  deleted = cur.rowcount
  conn.commit()
  conn.close()
  return {"compliance": "India DPDP Act 2023", "erased_customer": customer_id, "records_deleted": deleted}


@app.get("/security/audit-log")
def get_security_audit_log():
  return {"recent_events": SECURITY_AUDIT_LOG}


@app.get("/security/test-sqli")
def test_sql_injection_shield(customer_query: str):
  clean_val = sanitize_identifier(customer_query, field_name="customer_query")
  return {"status": "Safe input accepted", "sanitized_value": clean_val}