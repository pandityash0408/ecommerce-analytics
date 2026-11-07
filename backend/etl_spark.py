from datetime import datetime
import io
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from database import DB_PATH
import pandas as pd

# Set paths for the SQLite database file and Hadoop Parquet Data Lake folder
BASE_DIR = os.getenv("DB_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_LAKE_DIR = os.path.join(BASE_DIR, "data_lake_hdfs")

# Synonym dictionary including Product/Description so product names are automatically extracted
COLUMN_SYNONYMS = {
    "CustomerID": [
        "customerid", "customer_id", "customer id", "customer", "customer_name",
        "customer name", "buyer", "client", "user_id", "userid", "name", "email", "phone",
    ],
    "InvoiceNo": [
        "invoiceno", "invoice_no", "invoice no", "invoice", "order_id", "order id",
        "orderid", "order_no", "bill_no", "transaction_id", "txn_id", "id",
    ],
    "InvoiceDate": [
        "invoicedate", "invoice_date", "invoice date", "date", "order_date",
        "order date", "orderdate", "timestamp", "purchase_date", "created_at", "time",
    ],
    "Product": [
        "description", "product", "product_name", "product name", "item",
        "item_name", "stockcode", "stock_code", "sku", "category", "title",
    ],
    "Quantity": [
        "quantity", "qty", "units", "count", "item_count", "items", "volume",
    ],
    "UnitPrice": [
        "unitprice", "unit_price", "unit price", "price", "amount", "total",
        "total_amount", "sales", "revenue", "value", "mrp", "cost", "rate",
    ],
    # Direct profit column synonyms if the CSV already contains profit
    "DirectProfit": [
        "profit", "net_profit", "net profit", "gross_profit", "margin", "earnings", "gain",
    ],
    # Making cost / COGS column synonyms to derive Profit = Revenue - Cost
    "MakingCost": [
        "making_cost", "making cost", "unit_cost", "unit cost", "cogs",
        "cost_price", "cost price", "buying_price", "wholesale_price", "manufacturing_cost", "expense",
    ],
}


# Generates a clean dataset name and unique tenant_id directly from the uploaded file's name
def detect_store_from_csv(first_chunk: pd.DataFrame, filename: str):
  clean_filename = os.path.basename(filename or "dataset.csv").strip()
  slug = re.sub(r"[^a-z0-9]+", "_", clean_filename.lower()).strip("_")[:32]
  tenant_id = f"ds_{slug}"
  api_key = f"key-{slug}"
  return tenant_id, clean_filename, api_key


# Maps arbitrary CSV column names to our 6 standard model columns using fast vectorized operations
def auto_map_columns(df: pd.DataFrame):
  detected_mapping = {}
  lower_to_orig = {str(col).strip().lower(): col for col in df.columns}

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

    if matched_orig:
      df[target_col] = df[matched_orig]
      detected_mapping[target_col] = f"Mapped from '{matched_orig}'"
    else:
      if target_col == "Quantity":
        df["Quantity"] = 1
      elif target_col == "Product":
        df["Product"] = "Standard Item"
      elif target_col == "InvoiceNo":
        df["InvoiceNo"] = "INV-1"
      elif target_col == "InvoiceDate":
        df["InvoiceDate"] = datetime.today().strftime("%Y-%m-%d")
      elif target_col == "CustomerID":
        text_cols = df.select_dtypes(include=["object"]).columns.tolist()
        df["CustomerID"] = df[text_cols[0]].astype(str) if text_cols else "Guest"
      elif target_col == "UnitPrice":
        num_cols = df.select_dtypes(include=["number"]).columns.tolist()
        df["UnitPrice"] = df[num_cols[-1]] if num_cols else 100.0
      elif target_col in ("DirectProfit", "MakingCost"):
        # Set to None when the uploaded dataset does not contain a profit or cost column
        df[target_col] = None
        detected_mapping[target_col] = "Not present in dataset"

  return df, detected_mapping


# Cleans a single DataFrame chunk using fast vectorized C-string operations
# Cleans a single DataFrame chunk and derives Profit from DirectProfit or MakingCost
def clean_chunk_fast(chunk: pd.DataFrame, tenant_id: str):
  chunk.columns = [str(c).strip() for c in chunk.columns]
  mapped_chunk, schema_mapping = auto_map_columns(chunk)

  # Convert Quantity and UnitPrice to numeric values cleanly
  mapped_chunk["Quantity"] = pd.to_numeric(mapped_chunk["Quantity"], errors="coerce")
  if mapped_chunk["UnitPrice"].dtype == object:
    mapped_chunk["UnitPrice"] = pd.to_numeric(
        mapped_chunk["UnitPrice"].astype(str).str.replace(r"[₹$,]", "", regex=True),
        errors="coerce",
    )
  else:
    mapped_chunk["UnitPrice"] = pd.to_numeric(mapped_chunk["UnitPrice"], errors="coerce")

  mapped_chunk["InvoiceDate"] = mapped_chunk["InvoiceDate"].astype(str).str.slice(0, 10)
  mapped_chunk["Product"] = mapped_chunk["Product"].fillna("Standard Item").astype(str)

  clean_chunk = mapped_chunk.dropna(
      subset=["CustomerID", "InvoiceNo", "Quantity", "UnitPrice"]
  ).copy()
  clean_chunk = clean_chunk[
      (clean_chunk["Quantity"] > 0) & (clean_chunk["UnitPrice"] > 0)
  ].copy()

  # Derive Profit: (1) DirectProfit column, or (2) Revenue - (Quantity * MakingCost), or (3) None
  revenue_series = clean_chunk["Quantity"] * clean_chunk["UnitPrice"]
  if "DirectProfit" in clean_chunk.columns and clean_chunk["DirectProfit"].notna().any():
    clean_chunk["Profit"] = pd.to_numeric(
        clean_chunk["DirectProfit"].astype(str).str.replace(r"[₹$,]", "", regex=True),
        errors="coerce",
    ).round(2)
  elif "MakingCost" in clean_chunk.columns and clean_chunk["MakingCost"].notna().any():
    unit_cost = pd.to_numeric(
        clean_chunk["MakingCost"].astype(str).str.replace(r"[₹$,]", "", regex=True),
        errors="coerce",
    )
    clean_chunk["Profit"] = (revenue_series - (clean_chunk["Quantity"] * unit_cost)).round(2)
  else:
    clean_chunk["Profit"] = None

  clean_chunk["tenant_id"] = tenant_id
  clean_chunk["CustomerID"] = clean_chunk["CustomerID"].astype(str).str.replace(".0", "", regex=False)
  return clean_chunk, schema_mapping


# Streams any supported file format in 100,000-row chunks
def iterate_any_file_in_chunks(file_path: str, filename: str):
  fname = (filename or "data.csv").lower()

  if fname.endswith(".zip"):
    with zipfile.ZipFile(file_path) as z:
      inner_files = [f for f in z.namelist() if not f.startswith("__MACOSX") and not f.endswith("/")]
      if inner_files:
        with z.open(inner_files[0]) as inner_fp:
          yield from pd.read_csv(inner_fp, chunksize=100000, encoding="utf-8", encoding_errors="replace", low_memory=False, on_bad_lines="skip")
    return

  if fname.endswith(".xlsx") or fname.endswith(".xls"):
    df = pd.read_excel(file_path)
    for start in range(0, len(df), 100000):
      yield df.iloc[start : start + 100000].copy()
  elif fname.endswith(".parquet"):
    df = pd.read_parquet(file_path)
    for start in range(0, len(df), 100000):
      yield df.iloc[start : start + 100000].copy()
  elif fname.endswith(".json") or fname.endswith(".jsonl"):
    df = pd.read_json(file_path, lines=fname.endswith(".jsonl"))
    for start in range(0, len(df), 100000):
      yield df.iloc[start : start + 100000].copy()
  elif fname.endswith(".xml"):
    df = pd.read_xml(file_path)
    for start in range(0, len(df), 100000):
      yield df.iloc[start : start + 100000].copy()
  elif fname.endswith(".tsv") or fname.endswith(".txt"):
    yield from pd.read_csv(file_path, sep="\t", chunksize=100000, encoding="utf-8", encoding_errors="replace", low_memory=False, on_bad_lines="skip")
  else:
    comp = "gzip" if fname.endswith(".gz") else "infer"
    yield from pd.read_csv(file_path, compression=comp, chunksize=100000, encoding="utf-8", encoding_errors="replace", low_memory=False, on_bad_lines="skip")


# Background worker that finishes loading chunks 2..N for massive 1M+ row files without blocking the UI
def _background_ingest_remaining_chunks(temp_path: str, filename: str, tenant_id: str):
  try:
    conn = sqlite3.connect(DB_PATH, timeout=120)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")

    chunk_gen = iterate_any_file_in_chunks(temp_path, filename)
    # Skip chunk 0 because it was already loaded synchronously for instant UI display
    next(chunk_gen, None)

    for chunk in chunk_gen:
      clean_chunk, _ = clean_chunk_fast(chunk, tenant_id)
      if not clean_chunk.empty:
        # Include the derived or nullable Profit column when inserting into SQLite
        db_cols = clean_chunk[["tenant_id", "InvoiceNo", "CustomerID", "InvoiceDate", "Product", "Quantity", "UnitPrice", "Profit"]]
        db_cols.to_sql("sales", conn, if_exists="append", index=False, chunksize=10000)
        conn.commit()

    conn.close()
  finally:
    if os.path.exists(temp_path):
      os.remove(temp_path)


# Loads the first 100k rows immediately (<2 seconds) so the UI updates right away, and streams the rest in background
def run_spark_etl_from_file(file_obj, tenant_id: str = None, filename: str = None):
  # Save uploaded stream to a fast local temporary file
  suffix = os.path.splitext(filename or "data.csv")[1] or ".csv"
  tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
  shutil.copyfileobj(file_obj, tmp)
  tmp.close()
  temp_path = tmp.name

  conn = sqlite3.connect(DB_PATH, timeout=120)
  conn.execute("PRAGMA journal_mode=WAL;")
  conn.execute("PRAGMA synchronous=OFF;")
  conn.execute("PRAGMA temp_store=MEMORY;")

  chunk_gen = iterate_any_file_in_chunks(temp_path, filename or "sales.csv")
  first_chunk = next(chunk_gen, pd.DataFrame())

  if first_chunk.empty:
    conn.close()
    os.remove(temp_path)
    return {"status": "Empty dataset", "tenant_id": tenant_id, "store_name": filename, "api_key": "", "extract_raw_rows": 0, "transform_dirty_rows_removed": 0, "load_clean_rows_saved": 0}

  first_chunk.columns = [str(c).strip() for c in first_chunk.columns]
  if filename:
    tenant_id, store_name, api_key = detect_store_from_csv(first_chunk, filename)
    conn.execute(
        "INSERT OR REPLACE INTO stores (tenant_id, store_name, api_key, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (tenant_id, store_name, api_key),
    )
    conn.execute("DELETE FROM sales WHERE tenant_id = ?", (tenant_id,))
  else:
    store_name = tenant_id
    api_key = "key-sample-sales"

  clean_first, schema_mapping = clean_chunk_fast(first_chunk, tenant_id)
  # MUST include "Profit" in db_cols so SQLite saves the derived profit column!
  db_cols = clean_first[["tenant_id", "InvoiceNo", "CustomerID", "InvoiceDate", "Product", "Quantity", "UnitPrice", "Profit"]]
  db_cols.to_sql("sales", conn, if_exists="append", index=False, chunksize=10000)
  conn.commit()
  conn.close()

  # Write sample Parquet file to Hadoop Data Lake
  tenant_lake_path = os.path.join(DATA_LAKE_DIR, f"tenant_id={tenant_id}")
  os.makedirs(tenant_lake_path, exist_ok=True)
  clean_first.head(25000).to_parquet(os.path.join(tenant_lake_path, "sales_part_0001.parquet"), index=False)

  # If the file has more than 100,000 rows, stream the remaining chunks in a background thread!
  if len(first_chunk) == 100000:
    bg_thread = threading.Thread(
        target=_background_ingest_remaining_chunks,
        args=(temp_path, filename or "sales.csv", tenant_id),
        daemon=True,
    )
    bg_thread.start()
  else:
    os.remove(temp_path)

  return {
      "status": "Instant Dataset Load Complete (Background streaming active for 100k+ rows)",
      "tenant_id": tenant_id,
      "store_name": store_name,
      "api_key": api_key,
      "detected_column_mapping": schema_mapping,
      "extract_raw_rows": len(first_chunk),
      "transform_dirty_rows_removed": len(first_chunk) - len(clean_first),
      "load_clean_rows_saved": len(clean_first),
      "hadoop_data_lake_path": f"data_lake_hdfs/tenant_id={tenant_id}/sales_part_0001.parquet",
  }


# Wrapper for byte-buffer ETL calls
def run_spark_etl(csv_bytes: bytes, tenant_id: str):
  return run_spark_etl_from_file(io.BytesIO(csv_bytes), tenant_id=tenant_id)