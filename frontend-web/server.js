const express = require("express");
const cors = require("cors");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.static(path.join(__dirname, "public")));

// 1. Store Insights (RFM + K-Means + CLV + Reviews + Bundles + Cohorts)
app.get("/api/insights", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-store-a-123";
    const response = await fetch(`${BACKEND_URL}/store-insights`, {
      headers: { "X-API-Key": apiKey },
    });
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ detail: "Express Gateway Error: " + err.message });
  }
});

// 2. Customer 360 & SHAP Explainability
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

// 3. Universal CSV Upload -> Forwards to FastAPI PySpark ETL & Hadoop Data Lake
app.post("/api/etl-upload", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-store-a-123";
    const { filename, csvText } = req.body;

    const formData = new FormData();
    const blob = new Blob([csvText], { type: "text/csv" });
    formData.append("file", blob, filename || "uploaded_sales.csv");

    const response = await fetch(`${BACKEND_URL}/etl/upload`, {
      method: "POST",
      headers: { "X-API-Key": apiKey },
      body: formData,
    });
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// 4. India DPDP Act 2023 Right to Erasure
app.delete("/api/privacy/erase/:id", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-store-a-123";
    const response = await fetch(`${BACKEND_URL}/privacy/erase/${encodeURIComponent(req.params.id)}`, {
      method: "DELETE",
      headers: { "X-API-Key": apiKey },
    });
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// 5. Security Audit CCTV & SQLi Shield Test
app.get("/api/security/audit", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/security/audit-log`);
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`🚀 PulseIQ Express.js Frontend running on http://localhost:${PORT}`);
});