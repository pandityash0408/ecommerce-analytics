import os
import sqlite3

# Put the fridge (ecommerce.db) inside the backend folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ecommerce.db")


def init_db():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  # 1. Create the sales table with a tenant_id column (so stores never mix!)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            InvoiceNo TEXT NOT NULL,
            CustomerID TEXT NOT NULL,
            InvoiceDate TEXT NOT NULL,
            Quantity INTEGER NOT NULL,
            UnitPrice REAL NOT NULL
        )
    """)
  # Turbo-charge SQLite for millions of rows (Write-Ahead Logging + B-Tree Index)
  cursor.execute("PRAGMA journal_mode=WAL;")
  cursor.execute("PRAGMA synchronous=NORMAL;")
  cursor.execute(
      "CREATE INDEX IF NOT EXISTS idx_sales_tenant ON sales(tenant_id,"
      " CustomerID);"
  )

  # 2. If the fridge is empty, put starter sales in for Store A and Store B
  cursor.execute("SELECT COUNT(*) FROM sales")
  if cursor.fetchone()[0] == 0:
    sample_sales = [
        # Store A's customers (Priya, Alice, Bob)
        ("store_a", "536365", "Priya", "2026-10-30", 20, 100.0),
        ("store_a", "536366", "Priya", "2026-10-27", 15, 80.0),
        ("store_a", "536367", "Alice", "2026-10-29", 10, 50.0),
        ("store_a", "536368", "Bob", "2026-09-10", 2, 30.0),
        # Store B's customers (Vikram, Neha, Kabir)
        ("store_b", "900001", "Vikram", "2026-10-30", 50, 200.0),
        ("store_b", "900002", "Neha", "2026-10-28", 12, 150.0),
        ("store_b", "900003", "Kabir", "2026-08-01", 1, 90.0),
    ]
    cursor.executemany(
        """
            INSERT INTO sales (tenant_id, InvoiceNo, CustomerID, InvoiceDate, Quantity, UnitPrice)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
        sample_sales,
    )
    conn.commit()

  conn.close() 