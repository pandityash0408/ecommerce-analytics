from datetime import datetime, timedelta, timezone
import secrets
import sqlite3
from database import DB_PATH, init_db
from etl_spark import run_spark_etl
from fastapi import Depends, FastAPI, File, Form, HTTPException, Security, UploadFile
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
import jwt
import pandas as pd

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


# ==========================================
# NEW: BIG DATA SPARK ETL + HADOOP PARQUET DATA LAKE ENDPOINT
# ==========================================
@app.post("/etl/upload")
async def upload_sales_etl(
    file: UploadFile = File(...), store: dict = Security(verify_api_key)
):
  csv_bytes = await file.read()
  result = run_spark_etl(csv_bytes, tenant_id=store["tenant_id"])
  return result