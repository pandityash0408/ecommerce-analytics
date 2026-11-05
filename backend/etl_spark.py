from datetime import datetime
import io
import os
import re
import sqlite3
import zipfile
from database import DB_PATH
import pandas as pd

# Set paths for the SQLite database file and Hadoop Parquet Data Lake folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
}


# Generates a clean dataset name and unique tenant_id directly from the uploaded file's name
def detect_store_from_csv(first_chunk: pd.DataFrame, filename: str):
  clean_filename = os.path.basename(filename or "dataset.csv").strip()
  slug = re.sub(r"[^a-z0-9]+", "_", clean_filename.lower()).strip("_")[:32]
  tenant_id = f"ds_{slug}"
  api_key = f"key-{slug}"
  return tenant_id, clean_filename, api_key


# Automatically maps any uploaded column names to our 6 standard columns (including Product)
def auto_map_columns(df: pd.DataFrame):
  detected_mapping = {}
  lower_to_orig = {str(col).strip().lower(): col for col in df.columns}

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
      elif target_col == "Product":
        df["Product"] = "Standard Item"
        detected_mapping["Product"] = "Defaulted to 'Standard Item'"
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


# Detects the uploaded file extension (CSV, Excel, JSON, Parquet, TSV, XML, ZIP, GZ) and yields 100k-row chunks
def iterate_any_file_in_chunks(file_obj, filename: str):
  fname = (filename or "data.csv").lower()

  # Extract and stream the first dataset file if a .zip archive is uploaded
  if fname.endswith(".zip"):
    z = zipfile.ZipFile(file_obj)
    inner_files = [f for f in z.namelist() if not f.startswith("__MACOSX") and not f.endswith("/")]
    if not inner_files:
      raise ValueError("Uploaded ZIP archive is empty!")
    with z.open(inner_files[0]) as inner_fp:
      yield from iterate_any_file_in_chunks(inner_fp, inner_files[0])
    return

  # Read Excel workbooks (.xlsx, .xls) in 100k slices
  if fname.endswith(".xlsx") or fname.endswith(".xls"):
    df = pd.read_excel(file_obj)
    for start in range(0, len(df), 100000):
      yield df.iloc[start : start + 100000].copy()

  # Read Apache Parquet files (.parquet) in 100k slices
  elif fname.endswith(".parquet"):
    df = pd.read_parquet(file_obj)
    for start in range(0, len(df), 100000):
      yield df.iloc[start : start + 100000].copy()

  # Read JSON or JSON Lines (.json, .jsonl) in 100k slices
  elif fname.endswith(".json") or fname.endswith(".jsonl"):
    try:
      df = pd.read_json(file_obj, lines=fname.endswith(".jsonl"))
    except ValueError:
      file_obj.seek(0)
      df = pd.read_json(file_obj, lines=True)
    for start in range(0, len(df), 100000):
      yield df.iloc[start : start + 100000].copy()

  # Read XML files (.xml) in 100k slices
  elif fname.endswith(".xml"):
    df = pd.read_xml(file_obj)
    for start in range(0, len(df), 100000):
      yield df.iloc[start : start + 100000].copy()

  # Stream Tab-Separated files (.tsv, .txt) in 100k chunks
  elif fname.endswith(".tsv") or fname.endswith(".txt"):
    yield from pd.read_csv(
        file_obj, sep="\t", chunksize=100000, encoding="utf-8", encoding_errors="replace", low_memory=False, on_bad_lines="skip"
    )

  # Stream GZIP or standard CSV files in 100k chunks
  else:
    comp = "gzip" if fname.endswith(".gz") else "infer"
    yield from pd.read_csv(
        file_obj, compression=comp, chunksize=100000, encoding="utf-8", encoding_errors="replace", low_memory=False, on_bad_lines="skip"
    )


# Streams any supported file format, saves the dataset entry in SQLite, and loads 100k-row batches
def run_spark_etl_from_file(file_obj, tenant_id: str = None, filename: str = None):
  raw_row_count = 0
  clean_row_count = 0
  schema_mapping = {}
  first_chunk_sample = None
  store_name = None
  api_key = None

  conn = sqlite3.connect(DB_PATH, timeout=60)
  conn.execute("PRAGMA journal_mode=WAL;")
  conn.execute("PRAGMA synchronous=NORMAL;")

  for chunk in iterate_any_file_in_chunks(file_obj, filename or "sales.csv"):
    chunk.columns = [str(c).strip() for c in chunk.columns]
    raw_row_count += len(chunk)

    # Register the dataset filename in the stores table on the first chunk
    if first_chunk_sample is None and filename:
      tenant_id, store_name, api_key = detect_store_from_csv(chunk, filename)
      conn.execute(
          "INSERT OR REPLACE INTO stores (tenant_id, store_name, api_key, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
          (tenant_id, store_name, api_key),
      )
      conn.execute("DELETE FROM sales WHERE tenant_id = ?", (tenant_id,))

    mapped_chunk, schema_mapping = auto_map_columns(chunk)

    # Convert Quantity and UnitPrice to numeric values and standardize dates
    mapped_chunk["Quantity"] = pd.to_numeric(mapped_chunk["Quantity"], errors="coerce")
    mapped_chunk["UnitPrice"] = pd.to_numeric(
        mapped_chunk["UnitPrice"].astype(str).str.replace(r"[₹$,]", "", regex=True),
        errors="coerce",
    )
    mapped_chunk["InvoiceDate"] = mapped_chunk["InvoiceDate"].astype(str).str.slice(0, 10)
    mapped_chunk["Product"] = mapped_chunk["Product"].fillna("Standard Item").astype(str).str.strip()

    # Remove invalid rows (missing CustomerID or non-positive Quantity/UnitPrice)
    clean_chunk = mapped_chunk.dropna(
        subset=["CustomerID", "InvoiceNo", "Quantity", "UnitPrice"]
    ).copy()
    clean_chunk = clean_chunk[
        (clean_chunk["Quantity"] > 0)
        & (clean_chunk["UnitPrice"] > 0)
        & (clean_chunk["CustomerID"].astype(str).str.strip() != "")
        & (clean_chunk["CustomerID"].astype(str).str.lower() != "nan")
    ].copy()

    clean_chunk["tenant_id"] = tenant_id
    clean_chunk["CustomerID"] = (
        clean_chunk["CustomerID"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    clean_row_count += len(clean_chunk)

    if first_chunk_sample is None and not clean_chunk.empty:
      first_chunk_sample = clean_chunk.head(50000).copy()

    # Bulk-insert the cleaned batch including the Product column into SQLite
    db_cols = clean_chunk[[
        "tenant_id", "InvoiceNo", "CustomerID", "InvoiceDate", "Product", "Quantity", "UnitPrice"
    ]]
    db_cols.to_sql("sales", conn, if_exists="append", index=False)

  conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_tenant ON sales(tenant_id, CustomerID);")
  conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(tenant_id, Product);")
  conn.commit()
  conn.close()

  # Save partitioned Apache Parquet file to Hadoop Data Lake directory
  tenant_lake_path = os.path.join(DATA_LAKE_DIR, f"tenant_id={tenant_id}")
  os.makedirs(tenant_lake_path, exist_ok=True)
  parquet_file = os.path.join(tenant_lake_path, "sales_part_0001.parquet")
  if first_chunk_sample is not None:
    first_chunk_sample.to_parquet(parquet_file, index=False)

  return {
      "status": "Dataset Processed Successfully",
      "tenant_id": tenant_id,
      "store_name": store_name or tenant_id,
      "api_key": api_key,
      "detected_column_mapping": schema_mapping,
      "extract_raw_rows": raw_row_count,
      "transform_dirty_rows_removed": raw_row_count - clean_row_count,
      "load_clean_rows_saved": clean_row_count,
      "hadoop_data_lake_path": f"data_lake_hdfs/tenant_id={tenant_id}/sales_part_0001.parquet",
  }


# Wrapper for byte-buffer ETL calls
def run_spark_etl(csv_bytes: bytes, tenant_id: str):
  return run_spark_etl_from_file(io.BytesIO(csv_bytes), tenant_id=tenant_id)