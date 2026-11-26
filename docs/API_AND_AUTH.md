# API and Authentication Guide

## Base URLs and API Tooling

When running locally, FastAPI is available at `http://localhost:8000`. Interactive documentation is served at `/docs` (Swagger UI) and `/redoc` (ReDoc). Import `postman/ecommerce-analytics.postman_collection.json` into Postman to exercise the configured requests.

Unless noted otherwise, protected dataset endpoints use the tenant resolved from a valid `X-API-Key`. When requests pass through the authenticated website gateway, it also sends `X-User-Id`; the backend checks it against the dataset `owner_id` for strict per-user isolation.

## FastAPI Endpoint Reference

| Method | Endpoint | Authentication / input | Purpose |
| --- | --- | --- | --- |
| GET | `/docs` | None | Swagger UI / OpenAPI explorer. |
| GET | `/redoc` | None | ReDoc API reference. |
| GET | `/openapi.json` | None | OpenAPI schema document. |
| GET | `/stores` | Optional `X-User-Id` | Lists datasets; with `X-User-Id`, returns only that user's datasets. |
| DELETE | `/stores/{tenant_id}` | `X-User-Id` for owner check | Deletes an uploaded dataset and its sales rows; another user's dataset is rejected. |
| GET | `/store-insights` | `X-API-Key` | Returns KPIs, RFM segments, K-Means tiers, product leaderboard, locations, and customer behavior. |
| GET | `/products/search` | `X-API-Key`; optional `q` | Searches tenant products, returning revenue and units. |
| GET | `/products/trends` | `X-API-Key`; `granularity`, `start_period`, `end_period`, `country`, `products` | Returns selected product revenue, unit, and available profit time series. |
| GET | `/hello` | None | Lightweight service response. |
| GET | `/rfm` | `X-API-Key` | Returns tenant RFM customer data. |
| POST | `/login-basic` | HTTP Basic credentials | Authenticates a Basic user and issues a 30-minute HS256 Bearer JWT. |
| GET | `/rfm-jwt` | `Authorization: Bearer <JWT>` | Returns RFM records for the tenant encoded in the JWT. |
| POST | `/oauth/authorize` | Form: `username`, `password` | Validates a resource owner and returns a one-time authorization code. |
| POST | `/oauth/token` | Form grant parameters | Exchanges an authorization code or client credentials for a Bearer JWT. |
| GET | `/ml/churn` | Bearer JWT with `ml:predict`; optional `tenant_id` | Produces per-customer churn probability and status. |
| POST | `/etl/upload` | Multipart `file`; optional `X-User-Id` | Ingests a sales file into SQLite/Parquet under the authenticated owner identity. |
| GET | `/customer-360/{customer_id}` | `X-API-Key` | Returns verified spend, order history, and customer-level drivers. |
| DELETE | `/privacy/erase/{customer_id}` | `X-API-Key` | Erases the named customer from the authorized tenant under India DPDP Act 2023. |
| GET | `/security/audit-log` | None | Returns recent CyberArmor security events. |
| GET | `/security/test-sqli` | Query `customer_query` | Exercises identifier sanitization / SQL-injection shielding. |
| POST | `/webhooks/register` | JSON: `target_url`, optional `event_type`, `description` | Registers an outbound event webhook. |
| GET | `/webhooks` | None | Lists registered webhooks and recent delivery logs. |
| POST | `/webhooks/trigger-test` | Optional `event_type`, `message` | Sends an HMAC-signed test event to matching subscribers. |
| POST | `/webhooks/github` | GitHub headers and raw body | Receives GitHub events and verifies the HMAC signature when supplied. |

## Backend Authentication Flows

| # | Flow | How it works | Typical endpoint |
| --- | --- | --- | --- |
| 1 | API Key | Send `X-API-Key`. The backend resolves its tenant and, if `X-User-Id` is present, verifies dataset ownership. | `/rfm`, `/store-insights` |
| 2 | HTTP Basic Auth | Send `Authorization: Basic <base64(username:password)>`. A valid user can exchange Basic credentials for a short-lived Bearer token. | `/login-basic` |
| 3 | Bearer Token | Send `Authorization: Bearer <token>`. Missing tokens are rejected before protected handlers execute. | `/rfm-jwt`, `/ml/churn` |
| 4 | JWT (HS256) | The backend validates the HS256 signature and expiry, then uses claims such as `sub`, `tenant_id`, `store_name`, and `scopes`. | `/rfm-jwt` |
| 5 | OAuth 2.0 Authorization Code | Authenticate at `/oauth/authorize`, receive a one-time code, then exchange it at `/oauth/token` using `grant_type=authorization_code`. The resulting JWT carries the user's tenant and scopes. | `/oauth/authorize` → `/oauth/token` |
| 6 | OAuth 2.0 Client Credentials | A machine client posts its ID and secret to `/oauth/token` with `grant_type=client_credentials`; the token contains `ml:predict` for service-to-service churn requests. | `/oauth/token` → `/ml/churn` |

### API Key example

```bash
curl http://localhost:8000/rfm \
  -H "X-API-Key: <your-api-key>" \
  -H "X-User-Id: <signed-in-user-id>"
```

### Basic-to-JWT example

```bash
curl -X POST http://localhost:8000/login-basic \
  -u '<username>:<password>'

curl http://localhost:8000/rfm-jwt \
  -H 'Authorization: Bearer <access_token>'
```

### OAuth token exchange examples

```bash
# Authorization Code
curl -X POST http://localhost:8000/oauth/token \
  -F 'grant_type=authorization_code' \
  -F 'code=<one-time-code>'

# Client Credentials
curl -X POST http://localhost:8000/oauth/token \
  -F 'grant_type=client_credentials' \
  -F 'client_id=<client-id>' \
  -F 'client_secret=<client-secret>'
```

Keep API keys, passwords, client secrets, JWTs, and webhook secrets out of repositories, browser code, screenshots, and Postman exports.

## Website Login: Password and Google OAuth 2.0 PKCE

The Express gateway on port 3000 owns the browser session. Its password route uses PBKDF2-HMAC-SHA256 and locks an account after five failed attempts. On success, it issues a signed HttpOnly session cookie.

Google sign-in is a live OAuth 2.0 Authorization Code flow with PKCE S256 and CSRF protection:

1. The user opens `GET /auth/google` on the Express gateway.
2. The gateway generates a CSRF `state` value and a PKCE verifier/challenge using S256, stores the signed state in an HttpOnly cookie, then redirects to Google.
3. Google returns the authorization code and `state` to `GET /auth/google/callback`.
4. The gateway verifies the signed state, sends the code and PKCE verifier to Google's token endpoint server-side, and validates the returned identity.
5. The gateway creates its own HttpOnly signed session cookie. Protected dashboard requests use that session; the gateway forwards `X-User-Id` to FastAPI.

The web gateway routes its authenticated actions to the backend, including stores, insights, product search/trends, customer 360, ETL upload, dataset deletion, and customer erasure.

## Swagger UI and Postman

### Swagger UI

Open `http://localhost:8000/docs`, select an operation, choose **Try it out**, fill in its headers/body, and execute. Swagger is especially useful for inspecting schemas and checking response codes without assembling raw requests.

### Postman

1. Import `postman/ecommerce-analytics.postman_collection.json`.
2. Set the API base URL to `http://localhost:8000` (or your deployed HTTPS URL).
3. Set authorization values as collection variables rather than hard-coding secrets in requests.
4. Run the authentication request first, then copy its `access_token` into the Bearer token variable for JWT-protected requests.

## HMAC-SHA256 Webhooks

### Outbound events

Register a receiver with `POST /webhooks/register`, then call `POST /webhooks/trigger-test`. For each matching event subscription, the backend sends JSON with:

```text
Content-Type: application/json
X-Webhook-Event: <event-type>
X-Webhook-Signature: sha256=<hex-hmac>
```

The signature is HMAC-SHA256 over the **exact raw request body**, using the shared webhook secret. A receiver must calculate the HMAC using its copy of the secret and compare the complete `sha256=<digest>` value with a constant-time comparison.

```python
import hashlib
import hmac

expected = "sha256=" + hmac.new(
    webhook_secret.encode("utf-8"), raw_request_body, hashlib.sha256
).hexdigest()

is_valid = hmac.compare_digest(received_signature, expected)
```

Reject a webhook if the signature is missing or invalid; do not parse or act on an unverified body.

### Inbound GitHub events

Configure GitHub to send events to `POST /webhooks/github` using the same shared secret. GitHub delivers its signature in `X-Hub-Signature-256` and the event name in `X-GitHub-Event`. The endpoint records whether the signature verifies and logs the inbound delivery. Use the `ping` event and `/webhooks` delivery log to confirm setup before enabling automation based on push or pull-request events.
