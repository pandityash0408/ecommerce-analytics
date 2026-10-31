from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_hello():
  res = client.get("/hello")
  assert res.status_code == 200
  assert res.json() == {"message": "Hello from the kitchen!"}


def test_api_key_tenant_isolation():
  # Store A should ONLY see Store A's tenant_id
  res_a = client.get("/rfm", headers={"X-API-Key": "key-store-a-123"})
  assert res_a.status_code == 200
  assert res_a.json()["tenant_id"] == "store_a"

  # Store B should ONLY see Store B's tenant_id
  res_b = client.get("/rfm", headers={"X-API-Key": "key-store-b-456"})
  assert res_b.status_code == 200
  assert res_b.json()["tenant_id"] == "store_b"

  # Fake key must be rejected with 401 Unauthorized
  res_bad = client.get("/rfm", headers={"X-API-Key": "wrong-key"})
  assert res_bad.status_code == 401


def test_basic_and_jwt_auth():
  # 1. Login with Basic Auth
  login = client.post("/login-basic", auth=("alice", "passwordA"))
  assert login.status_code == 200
  token = login.json()["access_token"]

  # 2. Access protected JWT endpoint with Bearer token
  rfm = client.get("/rfm-jwt", headers={"Authorization": f"Bearer {token}"})
  assert rfm.status_code == 200
  assert rfm.json()["tenant_id"] == "store_a"