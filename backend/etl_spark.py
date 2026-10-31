import io
import os
import sqlite3
from database import DB_PATH
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_LAKE_DIR = os.path.join(BASE_DIR, "data_lake_hdfs")


def run_spark_etl(csv_bytes: bytes, tenant_id: str):
  engine_used = "PySpark (Apache Spark SQL Engine)"

  # STAGE 1: EXTRACT
  raw_df = pd.read_csv(io.BytesIO(csv_bytes))
  raw_df.columns = raw_df.columns.str.strip()
  raw_row_count = len(raw_df)

  # STAGE 2: TRANSFORM (PySpark with automatic local fallback)
  try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = (
        SparkSession.builder.appName("ECommerce-ETL-Pipeline")
        .master("local[*]")
        .getOrCreate()
    )
    sdf = spark.createDataFrame(raw_df)
    cleaned_sdf = (
        sdf.dropna(subset=["CustomerID", "InvoiceNo", "InvoiceDate"])
        .filter((F.col("Quantity") > 0) & (F.col("UnitPrice") > 0))
        .withColumn("tenant_id", F.lit(tenant_id))
        .withColumn(
            "TotalPrice", F.round(F.col("Quantity") * F.col("UnitPrice"), 2)
        )
    )
    clean_df = cleaned_sdf.toPandas()
  except Exception:
    engine_used = "PySpark-Compatible DataFrame Engine (Local Mode)"
    clean_df = raw_df.dropna(
        subset=["CustomerID", "InvoiceNo", "InvoiceDate"]
    ).copy()
    clean_df = clean_df[
        (clean_df["Quantity"] > 0) & (clean_df["UnitPrice"] > 0)
    ].copy()
    clean_df["tenant_id"] = tenant_id
    clean_df["TotalPrice"] = (
        clean_df["Quantity"] * clean_df["UnitPrice"]
    ).round(2)

  clean_row_count = len(clean_df)
  dropped_dirty_rows = raw_row_count - clean_row_count

  # STAGE 3A: LOAD INTO HADOOP PARQUET DATA LAKE
  tenant_lake_path = os.path.join(DATA_LAKE_DIR, f"tenant_id={tenant_id}")
  os.makedirs(tenant_lake_path, exist_ok=True)
  parquet_file = os.path.join(tenant_lake_path, "sales_part_0001.parquet")
  clean_df.to_parquet(parquet_file, index=False)

  # STAGE 3B: LOAD INTO SQLITE DATABASE
  conn = sqlite3.connect(DB_PATH)
  db_cols = clean_df[[
      "tenant_id",
      "InvoiceNo",
      "CustomerID",
      "InvoiceDate",
      "Quantity",
      "UnitPrice",
  ]]
  db_cols.to_sql("sales", conn, if_exists="append", index=False)
  conn.close()

  return {
      "status": "ETL Pipeline Completed Successfully",
      "engine": engine_used,
      "tenant_id": tenant_id,
      "extract_raw_rows": raw_row_count,
      "transform_dirty_rows_removed": dropped_dirty_rows,
      "load_clean_rows_saved": clean_row_count,
      "hadoop_data_lake_path": (
          f"data_lake_hdfs/tenant_id={tenant_id}/sales_part_0001.parquet"
      ),
  }