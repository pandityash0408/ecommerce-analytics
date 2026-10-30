from datetime import datetime, timedelta, timezone
import secrets
import sqlite3
from database import DB_PATH, init_db
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
import jwt
import pandas as pd

app = FastAPI(title="Intelligent E-Commerce Analytics API")

# 1. Start the Fridge
init_db()

# Secret stamp used by the kitchen to sign JWT wristbands
JWT_SECRET = "my-super-secret-kitchen-stamp-2026"
JWT_ALGORITHM = "HS256"

# ==========================================
# GUARD #1: API Key (X-API-Key Header)
# ==========================================
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


# ==========================================
# GUARD #2: Basic Auth (Username + Password)
# ==========================================
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


# ==========================================
# GUARD #3 & #4: Bearer Token + JWT Wristband
# ==========================================
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
    # Check the secret stamp and expiration time on the wristband
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return payload
  except jwt.ExpiredSignatureError:
    raise HTTPException(
        status_code=401,
        detail="Guard #4 (JWT): Your wristband expired! Please log in again.",
    )
  except jwt.InvalidTokenError:
    raise HTTPException(
        status_code=401,
        detail="Guard #4 (JWT): Fake or tampered JWT wristband!",
    )


# Helper function to calculate RFM for any tenant_id
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


# Endpoint 1: Protected by API Key
@app.get("/rfm")
def get_rfm_api_key(store: dict = Security(verify_api_key)):
  return {
      "auth_method": "API Key (X-API-Key)",
      "tenant_id": store["tenant_id"],
      "store_name": store["store_name"],
      "customers": calculate_rfm_for_tenant(store["tenant_id"]),
  }


# Endpoint 2: Ticket Booth! Protected by Basic Auth -> Issues a JWT Wristband
@app.post("/login-basic")
def login_with_basic_auth(user: dict = Depends(verify_basic_auth)):
  # Write user info + store tenant_id onto the JWT wristband
  payload = {
      "sub": user["username"],
      "tenant_id": user["tenant_id"],
      "store_name": user["store_name"],
      "scopes": user["scopes"],
      "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
  }
  token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
  return {
      "message": f"Welcome {user['username']}! Here is your JWT wristband.",
      "access_token": token,
      "token_type": "Bearer",
      "decoded_claims": payload,
  }


# Endpoint 3: Protected by Bearer Token + JWT Wristband
@app.get("/rfm-jwt")
def get_rfm_with_jwt(claims: dict = Security(verify_jwt_bearer)):
  return {
      "auth_method": "Bearer JWT Token",
      "logged_in_user": claims["sub"],
      "tenant_id": claims["tenant_id"],
      "store_name": claims["store_name"],
      "customers": calculate_rfm_for_tenant(claims["tenant_id"]),
  }