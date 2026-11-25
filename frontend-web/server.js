// Hardened Express.js Gateway with PBKDF2-SHA256 Auth, Brute-Force Lockout, HttpOnly Signed Cookies & Binary ETL Proxy
const express = require("express");
const cors = require("cors");
const path = require("path");
const crypto = require("crypto");

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const SESSION_SECRET = process.env.SESSION_SECRET || "capstone-hmac-session-secret-2026-x9k2p7";
const SESSION_COOKIE_NAME = "ecom_session";
const SESSION_TTL_MS = 4 * 60 * 60 * 1000;

function hashPassword(password, salt) {
  return crypto.pbkdf2Sync(password, salt, 100000, 32, "sha256").toString("hex");
}

function verifyPassword(password, salt, expectedHash) {
  const actual = Buffer.from(hashPassword(password, salt), "hex");
  const expected = Buffer.from(expectedHash, "hex");
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
}

const USERS = {
  yash: {
    salt: "salt_yash_cap_2026",
    hash: hashPassword(process.env.ADMIN_PASSWORD || "Yash@2026", "salt_yash_cap_2026"),
    role: "Administrator",
  },
  admin: {
    salt: "salt_admin_cap_2026",
    hash: hashPassword(process.env.ADMIN_PASSWORD || "Admin@2026", "salt_admin_cap_2026"),
    role: "Administrator",
  },
};

const failedLogins = new Map();
const MAX_FAILED_ATTEMPTS = 5;
const LOCKOUT_WINDOW_MS = 15 * 60 * 1000;

function checkBruteForce(ip) {
  const now = Date.now();
  const attempts = (failedLogins.get(ip) || []).filter((t) => now - t < LOCKOUT_WINDOW_MS);
  failedLogins.set(ip, attempts);
  return attempts.length >= MAX_FAILED_ATTEMPTS;
}

function recordFailedLogin(ip) {
  const attempts = failedLogins.get(ip) || [];
  attempts.push(Date.now());
  failedLogins.set(ip, attempts);
}

function createSessionToken(username, role) {
  const payload = Buffer.from(
    JSON.stringify({ u: username, r: role, exp: Date.now() + SESSION_TTL_MS })
  ).toString("base64url");
  const sig = crypto.createHmac("sha256", SESSION_SECRET).update(payload).digest("base64url");
  return `${payload}.${sig}`;
}

function verifySessionToken(token) {
  if (!token || !token.includes(".")) return null;
  const [payload, sig] = token.split(".");
  const expectedSig = crypto.createHmac("sha256", SESSION_SECRET).update(payload).digest("base64url");
  const a = Buffer.from(sig);
  const b = Buffer.from(expectedSig);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    if (!data.exp || Date.now() > data.exp) return null;
    return data;
  } catch {
    return null;
  }
}

function parseCookies(cookieHeader = "") {
  const out = {};
  cookieHeader.split(";").forEach((part) => {
    const idx = part.indexOf("=");
    if (idx > 0) {
      out[part.slice(0, idx).trim()] = decodeURIComponent(part.slice(idx + 1).trim());
    }
  });
  return out;
}

function requireAuth(req, res, next) {
  const cookies = parseCookies(req.headers.cookie);
  const session = verifySessionToken(cookies[SESSION_COOKIE_NAME]);
  if (!session) {
    if (req.path.startsWith("/api/")) {
      return res.status(401).json({ detail: "Unauthorized: Please sign in first." });
    }
    return res.redirect("/login");
  }
  req.user = session;
  next();
}

app.use(cors());
app.use(express.json({ limit: "25mb" }));

app.get("/login", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "login.html"));
});

app.post("/auth/login", (req, res) => {
  const clientIp = req.headers["x-forwarded-for"] || req.socket.remoteAddress || "127.0.0.1";
  if (checkBruteForce(clientIp)) {
    return res.status(429).json({ detail: "Too many failed login attempts. Locked for 15 minutes." });
  }

  const username = String(req.body?.username || "").trim().toLowerCase();
  const password = String(req.body?.password || "");
  const user = USERS[username];

  if (!user || !verifyPassword(password, user.salt, user.hash)) {
    recordFailedLogin(clientIp);
    return res.status(401).json({ detail: "Invalid username or password." });
  }

  failedLogins.delete(clientIp);
  const token = createSessionToken(username, user.role);
  const isHttps = req.headers["x-forwarded-proto"] === "https" || req.secure;
  const cookieFlags = [
    `${SESSION_COOKIE_NAME}=${encodeURIComponent(token)}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Strict",
    `Max-Age=${Math.floor(SESSION_TTL_MS / 1000)}`,
    isHttps ? "Secure" : "",
  ].filter(Boolean).join("; ");

  res.setHeader("Set-Cookie", cookieFlags);
  return res.json({ status: "authenticated", username, role: user.role });
});
// =====================================================================
// GOOGLE OAUTH 2.0 (Authorization Code Flow + PKCE S256 + CSRF State)
// =====================================================================
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID || "";
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET || "";
const OAUTH_STATE_COOKIE = "ecom_oauth_state";

function signOAuthState(obj) {
  const payload = Buffer.from(JSON.stringify(obj)).toString("base64url");
  const sig = crypto.createHmac("sha256", SESSION_SECRET).update(payload).digest("base64url");
  return `${payload}.${sig}`;
}

function verifyOAuthState(token) {
  if (!token || !token.includes(".")) return null;
  const [payload, sig] = token.split(".");
  const expected = crypto.createHmac("sha256", SESSION_SECRET).update(payload).digest("base64url");
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    return data.exp && Date.now() <= data.exp ? data : null;
  } catch {
    return null;
  }
}

// Step 1: Redirect browser to Google with cryptographic CSRF state + PKCE S256 challenge
app.get("/auth/google", (req, res) => {
  if (!GOOGLE_CLIENT_ID || !GOOGLE_CLIENT_SECRET) {
    return res.redirect("/login?error=Google+OAuth+is+not+configured+in+.env");
  }
  const proto = req.headers["x-forwarded-proto"] || (req.secure ? "https" : "http");
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const redirectUri = `${proto}://${host}/auth/google/callback`;

  const state = crypto.randomBytes(24).toString("base64url");
  const codeVerifier = crypto.randomBytes(32).toString("base64url");
  const codeChallenge = crypto.createHash("sha256").update(codeVerifier).digest("base64url");

  const signedState = signOAuthState({
    state,
    codeVerifier,
    redirectUri,
    exp: Date.now() + 10 * 60 * 1000,
  });

  const isHttps = proto === "https";
  res.setHeader(
    "Set-Cookie",
    [
      `${OAUTH_STATE_COOKIE}=${encodeURIComponent(signedState)}`,
      "Path=/",
      "HttpOnly",
      "SameSite=Lax",
      "Max-Age=600",
      isHttps ? "Secure" : "",
    ].filter(Boolean).join("; ")
  );

  const authUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  authUrl.searchParams.set("client_id", GOOGLE_CLIENT_ID);
  authUrl.searchParams.set("redirect_uri", redirectUri);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("scope", "openid email profile");
  authUrl.searchParams.set("state", state);
  authUrl.searchParams.set("code_challenge", codeChallenge);
  authUrl.searchParams.set("code_challenge_method", "S256");
  authUrl.searchParams.set("prompt", "select_account");

  return res.redirect(authUrl.toString());
});

// Step 2: Verify CSRF state, exchange code + PKCE verifier server-side with Google, and issue HttpOnly session cookie
app.get("/auth/google/callback", async (req, res) => {
  try {
    const { code, state } = req.query;
    const cookies = parseCookies(req.headers.cookie);
    const saved = verifyOAuthState(cookies[OAUTH_STATE_COOKIE]);

    if (!code || !state || !saved) {
      return res.redirect("/login?error=Invalid+or+expired+Google+OAuth+state");
    }

    const a = Buffer.from(String(state));
    const b = Buffer.from(String(saved.state));
    if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
      return res.redirect("/login?error=CSRF+state+mismatch");
    }

    const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code: String(code),
        client_id: GOOGLE_CLIENT_ID,
        client_secret: GOOGLE_CLIENT_SECRET,
        redirect_uri: saved.redirectUri,
        grant_type: "authorization_code",
        code_verifier: saved.codeVerifier,
      }),
    });
    const tokenData = await tokenRes.json();
    if (!tokenRes.ok || !tokenData.access_token) {
      return res.redirect("/login?error=Google+token+exchange+failed");
    }

    const userRes = await fetch("https://openidconnect.googleapis.com/v1/userinfo", {
      headers: { Authorization: `Bearer ${tokenData.access_token}` },
    });
    const profile = await userRes.json();
    if (!userRes.ok || !profile.email || !profile.email_verified) {
      return res.redirect("/login?error=Unverified+Google+account");
    }

    const sessionToken = createSessionToken(profile.email, "Google OAuth User");
    const isHttps = (req.headers["x-forwarded-proto"] || "") === "https" || req.secure;
    res.setHeader("Set-Cookie", [
      `${OAUTH_STATE_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`,
      [
        `${SESSION_COOKIE_NAME}=${encodeURIComponent(sessionToken)}`,
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
        `Max-Age=${Math.floor(SESSION_TTL_MS / 1000)}`,
        isHttps ? "Secure" : "",
      ].filter(Boolean).join("; "),
    ]);

    return res.redirect("/");
  } catch (err) {
    return res.redirect("/login?error=Google+sign-in+failed");
  }
});

app.post("/auth/logout", (req, res) => {
  res.setHeader("Set-Cookie", `${SESSION_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0`);
  return res.json({ status: "logged_out" });
});

app.get("/auth/me", requireAuth, (req, res) => {
  res.json({ username: req.user.u, role: req.user.r });
});

app.get("/", requireAuth, (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.get("/index.html", requireAuth, (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.use("/api", requireAuth);

// Helper that attaches the server-verified logged-in user (req.user.u) to every backend request
function backendHeaders(req) {
  return {
    "X-API-Key": req.headers["x-api-key"] || "",
    "X-User-Id": req.user.u,
  };
}

app.get("/api/stores", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/stores`, { headers: backendHeaders(req) });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.get("/api/insights", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/store-insights`, { headers: backendHeaders(req) });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.get("/api/products/search", async (req, res) => {
  try {
    const q = encodeURIComponent(req.query.q || "");
    const response = await fetch(`${BACKEND_URL}/products/search?q=${q}`, { headers: backendHeaders(req) });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.get("/api/products/trends", async (req, res) => {
  try {
    const rawQuery = req.originalUrl.includes("?") ? req.originalUrl.split("?")[1] : "";
    const response = await fetch(`${BACKEND_URL}/products/trends?${rawQuery}`, { headers: backendHeaders(req) });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.get("/api/customer-360/:id", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/customer-360/${encodeURIComponent(req.params.id)}`, {
      headers: backendHeaders(req),
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.delete("/api/privacy/erase/:id", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/privacy/erase/${encodeURIComponent(req.params.id)}`, {
      method: "DELETE",
      headers: backendHeaders(req),
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.post("/api/etl-chunk", async (req, res) => {
  try {
    const { filename, csvChunkText, fileBase64 } = req.body;
    const formData = new FormData();

    if (fileBase64) {
      const binaryBuf = Buffer.from(fileBase64, "base64");
      formData.append("file", new Blob([binaryBuf], { type: "application/octet-stream" }), filename);
    } else {
      formData.append("file", new Blob([csvChunkText || ""], { type: "text/csv" }), filename);
    }

    const response = await fetch(`${BACKEND_URL}/etl/upload`, {
      method: "POST",
      headers: backendHeaders(req),
      body: formData,
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.delete("/api/stores/:tenantId", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/stores/${encodeURIComponent(req.params.tenantId)}`, {
      method: "DELETE",
      headers: backendHeaders(req),
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Enterprise Analytics Dashboard (Auth Protected) running on http://localhost:${PORT}`);
});