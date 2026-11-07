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


# Validates X-API-Key against registered datasets in SQLite
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


# Returns all uploaded datasets ordered from newest to oldest
@app.get("/stores")
def list_all_stores():
  conn = sqlite3.connect(DB_PATH, timeout=60)
  df = pd.read_sql_query(
      "SELECT tenant_id, store_name, api_key, created_at FROM stores ORDER BY created_at DESC",
      conn,
  )
  conn.close()
  return {"stores": df.to_dict(orient="records")}


# Deletes an uploaded dataset and all of its sales rows when the user clicks 'x' in the left sidebar
@app.delete("/stores/{tenant_id}")
def delete_store_dataset(tenant_id: str):
  tenant_id = sanitize_identifier(tenant_id, "tenant_id")
  conn = sqlite3.connect(DB_PATH, timeout=60)
  cur = conn.cursor()
  cur.execute("DELETE FROM sales WHERE tenant_id = ?", (tenant_id,))
  cur.execute("DELETE FROM stores WHERE tenant_id = ?", (tenant_id,))
  conn.commit()
  conn.close()
  return {"status": "deleted", "tenant_id": tenant_id}


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


# Computes RFM and total products dealt with for the top 300 customers in SQL
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
        LIMIT 300
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


# Returns enterprise KPIs, Repeat Buyer Rate, Ranked K-Means Tiers, RFM Segment Matrix, and Top Products Leaderboard
@app.get("/store-insights")
def get_store_insights(store: dict = Security(verify_api_key)):
  tenant_id = store["tenant_id"]
  store_name = store["store_name"]

  conn = sqlite3.connect(DB_PATH, timeout=60)
  cur = conn.cursor()

  # 1. Query overall dataset revenue, customer count, and total orders
  cur.execute(
      "SELECT COALESCE(ROUND(SUM(Quantity * UnitPrice), 2), 0), COUNT(DISTINCT CustomerID), COUNT(DISTINCT InvoiceNo) FROM sales WHERE tenant_id = ?",
      (tenant_id,),
  )
  total_revenue, total_customers, total_orders = cur.fetchone()

  # 2. Query Repeat Customer Rate (% of customers with > 1 order)
  cur.execute(
      "SELECT COUNT(*) FROM (SELECT CustomerID FROM sales WHERE tenant_id = ? GROUP BY CustomerID HAVING COUNT(DISTINCT InvoiceNo) > 1)",
      (tenant_id,),
  )
  repeat_customers = cur.fetchone()[0]
  repeat_rate_pct = round((repeat_customers / total_customers) * 100, 1) if total_customers else 0.0

  # 3. Query Best Customer (highest spend + most products dealt with)
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

  # 4. Query Worst Customer (lowest spend + fewest products dealt with)
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

  # 5. Query Top 10 Products Leaderboard by Revenue & Units
  top_products_df = pd.read_sql_query(
      """
      SELECT
          Product,
          SUM(Quantity) AS Units_Sold,
          COUNT(DISTINCT CustomerID) AS Unique_Buyers,
          ROUND(SUM(Quantity * UnitPrice), 2) AS Revenue
      FROM sales
      WHERE tenant_id = ?
      GROUP BY Product
      ORDER BY Revenue DESC
      LIMIT 10
      """,
      conn,
      params=(tenant_id,),
  )
  conn.close()

  top_products = []
  for _, prow in top_products_df.iterrows():
    share = round(( float(prow["Revenue"]) / total_revenue ) * 100, 1) if total_revenue else 0.0
    top_products.append({
        "Product": prow["Product"],
        "Units_Sold": int(prow["Units_Sold"]),
        "Unique_Buyers": int(prow["Unique_Buyers"]),
        "Revenue": float(prow["Revenue"]),
        "Revenue_Share_%": share,
    })

  avg_spend = round(total_revenue / total_customers, 2) if total_customers else 0
  customers = calculate_rfm_for_tenant(tenant_id)

  # Run Scikit-Learn K-Means and rank clusters by average spend into Tier 1 (High), Tier 2 (Core), Tier 3 (Low)
  rfm_df = pd.DataFrame(customers)
  if len(rfm_df) >= 3:
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(rfm_df[["Recency", "Frequency", "Monetary"]])
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    raw_clusters = kmeans.fit_predict(scaled_features)
    rfm_df["raw_c"] = raw_clusters
    cluster_means = rfm_df.groupby("raw_c")["Monetary"].mean().sort_values(ascending=False).index.tolist()
    tier_labels = {
        cluster_means[0]: "Tier 1: High-Value",
        cluster_means[1]: "Tier 2: Core Regular",
        cluster_means[2]: "Tier 3: Low-Volume",
    }
    rfm_df["KMeans_Cluster"] = [tier_labels.get(c, "Tier 2: Core Regular") for c in raw_clusters]
  elif not rfm_df.empty:
    rfm_df["KMeans_Cluster"] = "Tier 1: High-Value"

  kmeans_map = dict(zip(rfm_df["CustomerID"], rfm_df["KMeans_Cluster"])) if not rfm_df.empty else {}

  enriched_customers = []
  segment_stats = {}

  for c in customers:
    r, f, m = c["Recency"], c["Frequency"], c["Monetary"]
    units = int(c.get("TotalProducts", f))

    if r <= 14 and (f >= 3 or m >= avg_spend * 1.5):
      segment = "Champions (VIP)"
    elif r <= 45 and f >= 2:
      segment = "Loyal Customers"
    elif r <= 90:
      segment = "At-Risk / Slipping"
    else:
      segment = "Hibernating / Inactive"

    if segment not in segment_stats:
      segment_stats[segment] = {"count": 0, "recency_sum": 0, "orders": 0, "revenue": 0.0}
    segment_stats[segment]["count"] += 1
    segment_stats[segment]["recency_sum"] += r
    segment_stats[segment]["orders"] += f
    segment_stats[segment]["revenue"] += m

    enriched_customers.append({
        "CustomerID": c["CustomerID"],
        "Segment": segment,
        "KMeans_ML_Cluster": kmeans_map.get(c["CustomerID"], "Tier 2: Core Regular"),
        "Recency_Days": r,
        "Orders": f,
        "Total_Products": units,
        "Total_Spent": m,
    })

  # Build Shopify-style RFM Segment Distribution Summary Matrix
  sample_total_cust = len(enriched_customers) or 1
  sample_total_rev = sum(c["Total_Spent"] for c in enriched_customers) or 1.0
  segment_summary = []
  for seg_name in ["Champions (VIP)", "Loyal Customers", "At-Risk / Slipping", "Hibernating / Inactive"]:
    st = segment_stats.get(seg_name, {"count": 0, "recency_sum": 0, "orders": 0, "revenue": 0.0})
    cnt = st["count"]
    segment_summary.append({
        "Segment": seg_name,
        "Customers": cnt,
        "Customer_Share_%": round((cnt / sample_total_cust) * 100, 1),
        "Avg_Recency_Days": round(st["recency_sum"] / cnt, 1) if cnt else 0,
        "Total_Orders": st["orders"],
        "Total_Revenue": round(st["revenue"], 2),
        "Revenue_Share_%": round((st["revenue"] / sample_total_rev) * 100, 1),
    })

  return {
      "store_name": store_name,
      "tenant_id": tenant_id,
      "kpis": {
          "total_revenue": total_revenue,
          "total_customers": total_customers,
          "total_orders": total_orders,
          "repeat_rate_pct": repeat_rate_pct,
          "avg_spend": avg_spend,
          "best_customer": best_customer,
          "worst_customer": worst_customer,
      },
      "segment_summary": segment_summary,
      "top_products": top_products,
      "customer_behavior": enriched_customers[:150],
  }


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


# Returns Year-wise or Month-wise product trends filtered between start_period (From) and end_period (To)
@app.get("/products/trends")
def get_product_trends(
    granularity: str = "month",
    start_period: str = "",
    end_period: str = "",
    products: list[str] = Query(default=[]),
    store: dict = Security(verify_api_key),
):
  tenant_id = store["tenant_id"]
  date_len = 4 if granularity == "year" else 7

  # Split any comma-delimited product strings into clean individual product names
  clean_products = []
  for p in products:
    for item in p.split(","):
      if item.strip() and item.strip() not in clean_products:
        clean_products.append(item.strip())
  products = clean_products

  conn = sqlite3.connect(DB_PATH, timeout=60)

  # Fetch all available years or year-months in this dataset to populate the client's From/To selectors
  periods_df = pd.read_sql_query(
      f"SELECT DISTINCT SUBSTR(InvoiceDate, 1, {date_len}) AS Period FROM sales WHERE tenant_id = ? ORDER BY Period ASC",
      conn,
      params=(tenant_id,),
  )
  all_available_periods = [p for p in periods_df["Period"].dropna().tolist() if len(str(p)) == date_len]

  # Default to top 3 products by revenue if none are explicitly selected yet
  if not products:
    top_df = pd.read_sql_query(
        "SELECT Product FROM sales WHERE tenant_id = ? GROUP BY Product ORDER BY SUM(Quantity * UnitPrice) DESC LIMIT 3",
        conn,
        params=(tenant_id,),
    )
    products = top_df["Product"].tolist()

  if not products or not all_available_periods:
    conn.close()
    return {"periods": [], "all_periods": all_available_periods, "series": [], "selected_products": []}

  # Apply From (start_period) and To (end_period) range bounds
  active_start = start_period if start_period in all_available_periods else all_available_periods[0]
  active_end = end_period if end_period in all_available_periods else all_available_periods[-1]
  if active_start > active_end:
    active_start, active_end = active_end, active_start

  placeholders = ",".join(["?"] * len(products))
  query = f"""
        SELECT
            SUBSTR(InvoiceDate, 1, {date_len}) AS Period,
            Product,
            ROUND(SUM(Quantity * UnitPrice), 2) AS Revenue,
            SUM(Quantity) AS Units
        FROM sales
        WHERE tenant_id = ?
          AND Product IN ({placeholders})
          AND SUBSTR(InvoiceDate, 1, {date_len}) >= ?
          AND SUBSTR(InvoiceDate, 1, {date_len}) <= ?
        GROUP BY Period, Product
        ORDER BY Period ASC
    """
  df = pd.read_sql_query(
      query, conn, params=[tenant_id] + list(products) + [active_start, active_end]
  )
  conn.close()

  filtered_periods = [p for p in all_available_periods if active_start <= p <= active_end]
  series = []
  for prod in products:
    prod_df = df[df["Product"] == prod].set_index("Period")
    series.append({
        "product": prod,
        "revenue": [float(prod_df.loc[p, "Revenue"]) if p in prod_df.index else 0.0 for p in filtered_periods],
        "units": [int(prod_df.loc[p, "Units"]) if p in prod_df.index else 0 for p in filtered_periods],
    })

  return {
      "granularity": granularity,
      "all_periods": all_available_periods,
      "start_period": active_start,
      "end_period": active_end,
      "periods": filtered_periods,
      "series": series,
      "selected_products": products,
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
      "FROM sales WHERE tenant_id = ? AND CustomerID = ? ORDER BY InvoiceDate DESC LIMIT 25",
      conn,
      params=(tenant_id, customer_id),
  )
  conn.close()
  if df.empty:
    raise HTTPException(status_code=404, detail="Customer not found.")
  total_spent = float(df["TotalPrice"].sum())
  orders_count = int(df["InvoiceNo"].nunique())
  total_units = int(df["Quantity"].sum())
  last_date = str(df["InvoiceDate"].max())
  shap_drivers = [
      {"Feature": "Last Purchase Date", "Impact": last_date},
      {"Feature": "Distinct Orders", "Impact": f"{orders_count} orders"},
      {"Feature": "Total Units Purchased", "Impact": f"{total_units:,} units"},
      {"Feature": "Total Verified Spend", "Impact": f"₹{total_spent:,.2f}"},
  ]
  return {
      "customer_id": customer_id,
      "store_name": store["store_name"],
      "total_spent": total_spent,
      "orders_count": orders_count,
      "last_order_date": last_date,
      "shap_explanations": shap_drivers,
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