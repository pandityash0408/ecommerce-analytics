# Intelligent E-Commerce Customer Behavior Analytics

An end-to-end, multi-tenant analytics platform for converting e-commerce transaction data into practical customer, product, and retention insights. The project pairs a FastAPI analytics service with a secure Express dashboard, automated ETL, and an HTTPS-ready deployment path.

## Architecture

```text
                         Internet users
                               |
                    Cloudflare Tunnel (cloudflared)
                               |
                    Nginx HTTPS reverse proxy
                         :80  ──>  :443
                         /                 \
                        /                   \
       Express web gateway :3000        FastAPI API :8000
       Tailwind + Chart.js dashboard     OWASP CyberArmorMiddleware
       frontend-web/server.js            backend/main.py
               |                                  |
               +---------- authenticated API -----+
                           requests with X-User-Id
                                                  |
                                  SQLite WAL + Parquet Data Lake
                           backend/database.py / backend/etl_spark.py
                                                  |
                              Docker volume: sqlite_data:/app/data
```

## Highlights

- Customer behavior analytics: RFM segmentation, ranked K-Means tiers, repeat-buyer rate, customer 360 views, product trends, and churn predictions.
- Multi-tenant data protection: uploaded datasets are scoped by `owner_id`; gateway requests carry `X-User-Id` so users can only access their own data.
- Security-first API: API key, Basic, Bearer, JWT, OAuth 2.0 Authorization Code, and OAuth 2.0 Client Credentials flows, plus OWASP-oriented request shielding.
- Secure web sign-in: PBKDF2-HMAC-SHA256 passwords, five-attempt lockout, HttpOnly signed session cookies, and live Google OAuth 2.0 using Authorization Code + PKCE S256 + CSRF state.
- Privacy support: India DPDP Act 2023 erasure through `DELETE /privacy/erase/{customer_id}`.
- Integration-ready operations: OpenAPI documentation, a Postman collection, and HMAC-SHA256 outbound and inbound GitHub webhooks.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Analytics API | Python, FastAPI (`backend/main.py`), port 8000 |
| Data platform | SQLite in WAL mode, Parquet Data Lake ETL (`backend/database.py`, `backend/etl_spark.py`) |
| Data persistence | Docker named volume `sqlite_data:/app/data` |
| API security | OWASP `CyberArmorMiddleware` (`backend/security_shield.py`) |
| Web gateway | Node.js, Express (`frontend-web/server.js`), port 3000 |
| Dashboard | Tailwind CSS and Chart.js (`frontend-web/public/index.html`) |
| Edge and transport | Nginx HTTPS reverse proxy (`nginx/`) and Cloudflare Tunnel (`cloudflared`) |
| Containers | Docker Compose |

## Quick Start

### Docker Compose

```bash
git clone https://github.com/pandityash0408/ecommerce-analytics.git
cd ecommerce-analytics
docker compose up --build -d
```

The services expose the backend on port `8000`, the web gateway on port `3000`, and Nginx on ports `80` and `443`.

### Windows helper

From the repository root, run:

```powershell
.\start.bat
```

## API Documentation and testing

- Swagger UI:`http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Postman collection: `postman/ecommerce-analytics.postman_collection.json`
- Full endpoint and authentication guide:[`docs/API_AND_AUTH.md`](docs/API_AND_AUTH.md)

## Privacy and Data Isolation

Website users authenticate with password or Google login and receive an HttpOnly signed cookie. The Express gateway forwards the authenticated identity in `X-User-Id`; FastAPI combines this identity with each dataset's `owner_id` to enforce tenant isolation. Customer erasure is available to an authorized dataset holder through the DPDP endpoint.

## Team

- Yash Pandit
- Kartikey Gupta
- Shashwat Upadhayaya
