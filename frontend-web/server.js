const express = require("express");
const cors = require("cors");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

app.use(cors());
// Allow raw CSV slices up to 25MB per chunk over same-origin HTTP
app.use(express.json({ limit: "25mb" }));
app.use(express.static(path.join(__dirname, "public")));

// Returns all saved datasets ordered from newest to oldest
app.get("/api/stores", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/stores`);
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Fetches executive KPIs (including Best & Worst Customer) and customer segments for a dataset
app.get("/api/insights", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-sample-sales";
    const response = await fetch(`${BACKEND_URL}/store-insights`, {
      headers: { "X-API-Key": apiKey },
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Searches distinct products in the active dataset by keyword
app.get("/api/products/search", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-sample-sales";
    const q = encodeURIComponent(req.query.q || "");
    const response = await fetch(`${BACKEND_URL}/products/search?q=${q}`, {
      headers: { "X-API-Key": apiKey },
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Fetches Year-wise or Month-wise sales trend series while preserving multiple 'products' query parameters
app.get("/api/products/trends", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-sample-sales";
    // Preserve multiple ?products=A&products=B parameters without joining them with a comma
    const rawQuery = req.originalUrl.includes("?") ? req.originalUrl.split("?")[1] : "";
    const response = await fetch(`${BACKEND_URL}/products/trends?${rawQuery}`, {
      headers: { "X-API-Key": apiKey },
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Fetches Customer 360 profile and order ledger
app.get("/api/customer-360/:id", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-sample-sales";
    const response = await fetch(`${BACKEND_URL}/customer-360/${encodeURIComponent(req.params.id)}`, {
      headers: { "X-API-Key": apiKey },
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Deletes a customer record under India DPDP Act 2023
app.delete("/api/privacy/erase/:id", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-sample-sales";
    const response = await fetch(`${BACKEND_URL}/privacy/erase/${encodeURIComponent(req.params.id)}`, {
      method: "DELETE",
      headers: { "X-API-Key": apiKey },
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Forwards 5MB file slices from browser to FastAPI backend over internal Docker network (zero CORS issues)
app.post("/api/etl-chunk", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-sample-sales";
    const { filename, csvChunkText } = req.body;
    const formData = new FormData();
    formData.append("file", new Blob([csvChunkText], { type: "text/csv" }), filename);

    const response = await fetch(`${BACKEND_URL}/etl/upload`, {
      method: "POST",
      headers: { "X-API-Key": apiKey },
      body: formData,
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Deletes a saved dataset from the sidebar when the user clicks the delete button
app.delete("/api/stores/:tenantId", async (req, res) => {
  try {
    const response = await fetch(`${BACKEND_URL}/stores/${encodeURIComponent(req.params.tenantId)}`, {
      method: "DELETE",
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// Proxies geographic product trends requests from the browser to the FastAPI backend
app.get("/api/products/geo-trends", async (req, res) => {
  try {
    const apiKey = req.headers["x-api-key"] || "key-sample-sales";
    const rawQuery = req.originalUrl.includes("?") ? req.originalUrl.split("?")[1] : "";
    const response = await fetch(`${BACKEND_URL}/products/geo-trends?${rawQuery}`, {
      headers: { "X-API-Key": apiKey },
    });
    res.status(response.status).json(await response.json());
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Enterprise Analytics Dashboard running on http://localhost:${PORT}`);
});