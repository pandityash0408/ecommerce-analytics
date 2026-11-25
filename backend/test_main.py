# Comprehensive Pytest Unit & Security Test Suite for FastAPI Backend (8 Tests)
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# 1. Health check endpoint
def test_hello():
  res = client.get("/hello")
  assert res.status_code == 200
  assert res.json() == {"message": "Hello from the kitchen!"}


# 2. Guard #1: Multi-tenant API Key isolation
def test_api_key_tenant_isolation():
  res_a = client.get("/rfm", headers={"X-API-Key": "key-store-a-123"})
  assert res_a.status_code == 200
  assert res_a.json()["tenant_id"] == "store_a"

  res_b = client.get("/rfm", headers={"X-API-Key": "key-store-b-456"})
  assert res_b.status_code == 200
  assert res_b.json()["tenant_id"] == "store_b"

  res_bad = client.get("/rfm", headers={"X-API-Key": "wrong-key"})
  assert res_bad.status_code == 401


# 3. Guards #2, #3, #4: HTTP Basic Auth -> Bearer JWT
def test_basic_and_jwt_auth():
  login = client.post("/login-basic", auth=("alice", "passwordA"))
  assert login.status_code == 200
  token = login.json()["access_token"]

  rfm = client.get("/rfm-jwt", headers={"Authorization": f"Bearer {token}"})
  assert rfm.status_code == 200
  assert rfm.json()["tenant_id"] == "store_a"


# 4. Guard #5: OAuth 2.0 Authorization Code Flow
def test_oauth2_authorization_code_flow():
  auth_res = client.post("/oauth/authorize", data={"username": "alice", "password": "passwordA"})
  assert auth_res.status_code == 200
  code = auth_res.json()["authorization_code"]

  tok_res = client.post("/oauth/token", data={"grant_type": "authorization_code", "code": code})
  assert tok_res.status_code == 200
  access_token = tok_res.json()["access_token"]

  rfm_res = client.get("/rfm-jwt", headers={"Authorization": f"Bearer {access_token}"})
  assert rfm_res.status_code == 200
  assert rfm_res.json()["tenant_id"] == "store_a"


# 5. Guard #6: OAuth 2.0 Client Credentials Flow (Machine-to-Machine ML Churn)
def test_oauth2_client_credentials_flow():
  tok_res = client.post(
      "/oauth/token",
      data={
          "grant_type": "client_credentials",
          "client_id": "analytics-robot",
          "client_secret": "robot-secret-999",
      },
  )
  assert tok_res.status_code == 200
  token = tok_res.json()["access_token"]

  ml_res = client.get("/ml/churn?tenant_id=store_a", headers={"Authorization": f"Bearer {token}"})
  assert ml_res.status_code == 200
  assert ml_res.json()["called_by_robot"] == "analytics-robot"


# 6. Store Insights KPIs & Product Trends (Month-wise and Year-wise)
def test_store_insights_and_trends():
  ins = client.get("/store-insights", headers={"X-API-Key": "key-sample-sales"})
  assert ins.status_code == 200
  assert "kpis" in ins.json()
  assert "top_products" in ins.json()

  trends_m = client.get("/products/trends?granularity=month", headers={"X-API-Key": "key-sample-sales"})
  assert trends_m.status_code == 200
  assert "periods" in trends_m.json()

  trends_y = client.get("/products/trends?granularity=year", headers={"X-API-Key": "key-sample-sales"})
  assert trends_y.status_code == 200
  assert trends_y.json()["granularity"] == "year"


# 7. OWASP CyberArmor SQL Injection Shield (Also verified by Jenkinsfile Stage 3)
def test_sql_injection_blocked():
  res = client.get("/security/test-sqli", params={"customer_query": "' OR 1=1 --"})
  assert res.status_code == 400
  audit = client.get("/security/audit-log")
  assert audit.status_code == 200
  assert len(audit.json()["recent_events"]) >= 1


# 8. WebHooks Registration, Signed Trigger & Inbound GitHub Receiver
def test_webhooks_register_trigger_and_github():
  reg = client.post(
      "/webhooks/register",
      json={"target_url": "http://127.0.0.1:9999/hook", "event_type": "dataset.uploaded", "description": "Unit Test Hook"},
  )
  assert reg.status_code == 200
  assert reg.json()["status"] == "registered"

  trig = client.post("/webhooks/trigger-test?event_type=dataset.uploaded")
  assert trig.status_code == 200
  assert trig.json()["signature"].startswith("sha256=")

  gh = client.post(
      "/webhooks/github",
      headers={"X-GitHub-Event": "push"},
      json={"repository": {"full_name": "pandityash0408/ecommerce-analytics"}, "pusher": {"name": "pandityash0408"}},
  )
  assert gh.status_code == 200
  assert gh.json()["github_event"] == "push"