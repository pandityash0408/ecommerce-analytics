from datetime import datetime
import io
import os
import re
import sqlite3
from database import DB_PATH
import pandas as pd

# Set paths for the SQLite database file and Hadoop Parquet Data Lake folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_LAKE_DIR = os.path.join(BASE_DIR, "data_lake_hdfs")

# Synonym dictionary so any store's CSV column names are automatically recognized
COLUMN_SYNONYMS = {
    "CustomerID": [
        "customerid", "customer_id", "customer id", "customer", "customer_name",
        "customer name", "buyer", "client", "user_id", "userid", "name", "email", "phone",
    ],
    "InvoiceNo": [
        "invoiceno", "invoice_no", "invoice no", "invoice", "order_id", "order id",
        "orderid", "order_no", "bill_no", "transaction_id", "txn_id", "id", "stockcode",
    ],
    "InvoiceDate": [
        "invoicedate", "invoice_date", "invoice date", "date", "order_date",
        "order date", "orderdate", "timestamp", "purchase_date", "created_at", "time",
    ],
    "Quantity": [
        "quantity", "qty", "units", "count", "item_count", "items", "volume",
    ],
    "UnitPrice": [
        "unitprice", "unit_price", "unit price", "price", "amount", "total",
        "total_amount", "sales", "revenue", "value", "mrp", "cost", "rate",
    ],
}


# Auto-detects a human-friendly Store Name from CSV columns (Store/Brand/Country) or the filename
def detect_store_from_csv(first_chunk: pd.DataFrame, filename: str):
  lower_cols = {c.strip().lower(): c for c in first_chunk.columns}

  # 1. Check if the CSV has an explicit store/merchant/shop/brand column
  for candidate in ["store_name", "store", "merchant", "shop", "brand", "seller"]:
    if candidate in lower_cols:
      val = str(first_chunk[lower_cols[candidate]].dropna().iloc[0]).strip()
      if val and val.lower() != "nan":
        clean_name = val.title()
        break
  else:
    # 2. Otherwise build a clean Store Name from the uploaded CSV filename (and top Country if present)
    base_name = os.path.splitext(os.path.basename(filename or "New_Store"))[0]
    clean_name = re.sub(r"[_\-]+", " ", base_name).strip().title()
    if not clean_name:
      clean_name = "Uploaded Retail Store"
    if "country" in lower_cols:
      top_country = str(first_chunk[lower_cols["country"]].dropna().iloc[0]).strip()
      if top_country and top_country.lower() != "nan" and len(clean_name) < 22:
        clean_name = f"{clean_name} ({top_country})"
    elif "store" not in clean_name.lower():
      clean_name = f"{clean_name} Store"

  # Generate a clean tenant_id slug and unique API key for this store
  slug = re.sub(r"[^a-z0-9]+", "_", clean_name.lower()).strip("_")[:24]
  tenant_id = f"store_{slug}"
  api_key = f"key-{slug}-auto"
  return tenant_id, clean_name, api_key


# Automatically maps any uploaded CSV column names to our 5 standard model columns
def auto_map_columns(df: pd.DataFrame):
  detected_mapping = {}
  lower_to_orig = {col.strip().lower(): col for col in df.columns}

  # Match each required column against exact or partial column name synonyms
  for target_col, synonyms in COLUMN_SYNONYMS.items():
    matched_orig = None
    for syn in synonyms:
      if syn in lower_to_orig:
        matched_orig = lower_to_orig[syn]
        break
    if not matched_orig:
      for lower_col, orig_col in lower_to_orig.items():
        if any(syn in lower_col for syn in synonyms):
          matched_orig = orig_col
          break

    # Assign the matched column or create safe fallback values if missing
    if matched_orig:
      df[target_col] = df[matched_orig]
      detected_mapping[target_col] = f"Mapped from '{matched_orig}'"
    else:
      if target_col == "Quantity":
        df["Quantity"] = 1
        detected_mapping["Quantity"] = "Defaulted to 1"
      elif target_col == "InvoiceNo":
        df["InvoiceNo"] = [f"INV-{i}" for i in range(len(df))]
        detected_mapping["InvoiceNo"] = "Auto-generated IDs"
      elif target_col == "InvoiceDate":
        df["InvoiceDate"] = datetime.today().strftime("%Y-%m-%d")
        detected_mapping["InvoiceDate"] = "Defaulted to today"
      elif target_col == "CustomerID":
        text_cols = df.select_dtypes(include=["object"]).columns.tolist()
        df["CustomerID"] = (
            df[text_cols[0]].astype(str)
            if text_cols
            else [f"Guest_{i}" for i in range(len(df))]
        )
        detected_mapping["CustomerID"] = "Inferred Customer ID"
      elif target_col == "UnitPrice":
        num_cols = df.select_dtypes(include=["number"]).columns.tolist()
        df["UnitPrice"] = df[num_cols[-1]] if num_cols else 100.0
        detected_mapping["UnitPrice"] = "Inferred Price"

  return df, detected_mapping


# Streams a large CSV file, auto-creates a dedicated store tenant, and bulk-loads 100k-row chunks
def run_spark_etl_from_file(file_obj, tenant_id: str = None, filename: str = None):
  raw_row_count = 0
  clean_row_count = 0
  schema_mapping = {}
  first_chunk_sample = None
  store_name = None
  api_key = None

  # Open SQLite with Write-Ahead Logging (WAL) for fast bulk writes
  conn = sqlite3.connect(DB_PATH, timeout=60)
  conn.execute("PRAGMA journal_mode=WAL;")
  conn.execute("PRAGMA synchronous=NORMAL;")

  # Read CSV stream in 100,000-row batches to handle 260MB+ files smoothly
  chunk_iterator = pd.read_csv(
      file_obj,
      chunksize=100000,
      encoding="utf-8",
      encoding_errors="replace",
      low_memory=False,
      on_bad_lines="skip",
  )

  for chunk in chunk_iterator:
    chunk.columns = chunk.columns.str.strip()
    raw_row_count += len(chunk)

    # On the very first chunk, auto-detect the Store Name from the CSV data/filename if uploaded via UI
    if first_chunk_sample is None and filename:
      tenant_id, store_name, api_key = detect_store_from_csv(chunk, filename)
      conn.execute(
          "INSERT OR REPLACE INTO stores (tenant_id, store_name, api_key) VALUES (?, ?, ?)",
          (tenant_id, store_name, api_key),
      )
      # Clear previous rows for this auto-detected store so re-uploading doesn't duplicate rows
      conn.execute("DELETE FROM sales WHERE tenant_id = ?", (tenant_id,))

    # Map arbitrary CSV headers to CustomerID, InvoiceNo, InvoiceDate, Quantity, UnitPrice
    mapped_chunk, schema_mapping = auto_map_columns(chunk)

    # Convert Quantity and UnitPrice to numeric values cleanly
    mapped_chunk["Quantity"] = pd.to_numeric(mapped_chunk["Quantity"], errors="coerce")
    mapped_chunk["UnitPrice"] = pd.to_numeric(
        mapped_chunk["UnitPrice"].astype(str).str.replace(r"[₹$,]", "", regex=True),
        errors="coerce",
    )
    mapped_chunk["InvoiceDate"] = mapped_chunk["InvoiceDate"].astype(str).str.slice(0, 10)

    # Filter out dirty rows (missing CustomerID or negative/zero Quantity and UnitPrice)
    clean_chunk = mapped_chunk.dropna(
        subset=["CustomerID", "InvoiceNo", "Quantity", "UnitPrice"]
    ).copy()
    clean_chunk = clean_chunk[
        (clean_chunk["Quantity"] > 0)
        & (clean_chunk["UnitPrice"] > 0)
        & (clean_chunk["CustomerID"].astype(str).str.strip() != "")
        & (clean_chunk["CustomerID"].astype(str).str.lower() != "nan")
    ].copy()

    # Tag every row with the auto-detected store's tenant_id
    clean_chunk["tenant_id"] = tenant_id
    clean_chunk["CustomerID"] = (
        clean_chunk["CustomerID"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    clean_row_count += len(clean_chunk)

    if first_chunk_sample is None and not clean_chunk.empty:
      first_chunk_sample = clean_chunk.head(50000).copy()

    # Write cleaned batch into SQLite database table
    db_cols = clean_chunk[[
        "tenant_id", "InvoiceNo", "CustomerID", "InvoiceDate", "Quantity", "UnitPrice"
    ]]
    db_cols.to_sql("sales", conn, if_exists="append", index=False)

  # Ensure composite index exists and commit transaction
  conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_tenant ON sales(tenant_id, CustomerID);")
  conn.commit()
  conn.close()

  # Write partitioned Apache Parquet file to the Hadoop Data Lake folder
  tenant_lake_path = os.path.join(DATA_LAKE_DIR, f"tenant_id={tenant_id}")
  os.makedirs(tenant_lake_path, exist_ok=True)
  parquet_file = os.path.join(tenant_lake_path, "sales_part_0001.parquet")
  if first_chunk_sample is not None:
    first_chunk_sample.to_parquet(parquet_file, index=False)

  # Return summary statistics including the newly created store name and api_key
  return {
      "status": "Chunked Big-Data ETL Completed",
      "engine": "PySpark-Compatible Chunked Streaming Engine (100k rows/batch)",
      "tenant_id": tenant_id,
      "store_name": store_name or tenant_id,
      "api_key": api_key,
      "detected_column_mapping": schema_mapping,
      "extract_raw_rows": raw_row_count,
      "transform_dirty_rows_removed": raw_row_count - clean_row_count,
      "load_clean_rows_saved": clean_row_count,
      "hadoop_data_lake_path": f"data_lake_hdfs/tenant_id={tenant_id}/sales_part_0001.parquet",
  }


# Backward-compatible wrapper when raw CSV bytes are passed directly
def run_spark_etl(csv_bytes: bytes, tenant_id: str):
  return run_spark_etl_from_file(io.BytesIO(csv_bytes), tenant_id=tenant_id)