from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import hmac
import re
import time
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

# ==========================================
# 1. CCTV SECURITY AUDIT LOG (Records blocked hacker attempts)
# ==========================================
SECURITY_AUDIT_LOG = []


def log_security_event(event_type: str, ip: str, detail: str, status: str):
  SECURITY_AUDIT_LOG.insert(
      0,
      {
          "timestamp_utc": (
              datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
          ),
          "event_type": event_type,
          "client_ip": ip,
          "status": status,
          "detail": detail,
      },
  )
  # Keep the latest 100 security events
  if len(SECURITY_AUDIT_LOG) > 100:
    SECURITY_AUDIT_LOG.pop()


# ==========================================
# 2. SALTED PBKDF2-SHA256 PASSWORD & SECRET HASHING
# ==========================================
SALT = b"capstone_india_2026_fixed_salt"


def hash_secret(plain_text: str) -> str:
  """Scrambles a password/secret using 100,000 rounds of PBKDF2-HMAC-SHA256."""
  dk = hashlib.pbkdf2_hmac("sha256", plain_text.encode("utf-8"), SALT, 100000)
  return dk.hex()


def verify_hashed_secret(plain_text: str, expected_hash: str) -> bool:
  """Constant-time comparison to prevent timing attacks."""
  actual_hash = hash_secret(plain_text)
  return hmac.compare_digest(actual_hash, expected_hash)


# ==========================================
# 3. SQL INJECTION & XSS INPUT SANITIZER
# ==========================================
DANGEROUS_PATTERNS = re.compile(
    r"(--|;|/\*|\*/|xp_|UNION\s+SELECT|DROP\s+TABLE|INSERT\s+INTO|<script|javascript:)",
    re.IGNORECASE,
)


def sanitize_identifier(value: str, field_name: str = "Input") -> str:
  if not value or len(value) > 100:
    raise HTTPException(status_code=400, detail=f"Invalid {field_name} length.")
  if DANGEROUS_PATTERNS.search(value) or "'" in value or '"' in value:
    log_security_event(
        "SQLi/XSS Attempt Blocked",
        "client",
        f"Blocked malicious payload in {field_name}: {value}",
        "BLOCKED (400)",
    )
    raise HTTPException(
        status_code=400,
        detail=(
            "🛡️ Security Shield Blocked: Malicious characters detected in"
            f" {field_name}!"
        ),
    )
  return value.strip()


# ==========================================
# 4. RATE LIMITER + OWASP SECURITY HEADERS MIDDLEWARE
# ==========================================
class CyberArmorMiddleware(BaseHTTPMiddleware):

  def __init__(self, app, max_requests_per_minute: int = 120):
    super().__init__(app)
    self.max_requests = max_requests_per_minute
    self.request_Give_log = defaultdict(list)

  async def dispatch(self, request: Request, call_next):
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()

    # Clean requests older than 60 seconds
    self.request_Give_log[client_ip] = [
        t for t in self.request_Give_log[client_ip] if now - t < 60
    ]

    if len(self.request_Give_log[client_ip]) >= self.max_requests:
      log_security_event(
          "DDoS / Rate Limit Exceeded",
          client_ip,
          f"Exceeded {self.max_requests} requests/min",
          "BLOCKED (429)",
      )
      from fastapi.responses import JSONResponse

      return JSONResponse(
          status_code=429,
          content={
              "detail": (
                  "🛡️ Rate Limit Shield: Too many requests! Slow down and try"
                  " again in 1 minute."
              )
          },
      )

    self.request_Give_log[client_ip].append(now)

    response = await call_next(request)

    # Add OWASP Hardening Headers to every response
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'none';"
    )
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response
  