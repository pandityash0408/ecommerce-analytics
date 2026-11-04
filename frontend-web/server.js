const express = require("express");
const cors = require("cors");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// Express API Gateway Route 1: Fetch Store Insights from Python FastAPI Backend
app.get("/api/insights", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-store-a-123";
    const response = await fetch(`${BACKEND_URL}/store-insights`, {
      headers: { "X-API-Key": apiKey },
    });
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ detail: "Express Gateway could not reach FastAPI Backend: " + err.message });
  }
});

// Express API Gateway Route 2: Fetch Customer 360 Profile & SHAP Drivers
app.get("/api/customer-360/:id", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-store-a-123";
    const response = await fetch(`${BACKEND_URL}/customer-360/${encodeURIComponent(req.params.id)}`, {
      headers: { "X-API-Key": apiKey },
    });
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Express API Gateway Route 3: Security Audit Log & SQLi Test
app.get("/api/security/audit", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/security/audit-log`);
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`🚀 PulseIQ Express.js Frontend & API Gateway running on http://localhost:${PORT}`);
});