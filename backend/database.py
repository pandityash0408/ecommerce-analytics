import os
import sqlite3

# Define the path to the SQLite database file inside the backend directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ecommerce.db")


# Initializes the sales table, the dynamic stores registry table, and starter data
def init_db():
  conn = sqlite3.connect(DB_PATH, timeout=60)
  cursor = conn.cursor()

  # Enable Write-Ahead Logging (WAL) for high-speed million-row reads and writes
  cursor.execute("PRAGMA journal_mode=WAL;")
  cursor.execute("PRAGMA synchronous=NORMAL;")

  # Create the stores table to store dynamically created stores from uploaded CSV files
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            tenant_id TEXT PRIMARY KEY,
            store_name TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL
        )
    """)

  # Seed the default two demo stores if the stores table is empty
  cursor.execute("SELECT COUNT(*) FROM stores")
  if cursor.fetchone()[0] == 0:
    cursor.executemany(
        "INSERT INTO stores (tenant_id, store_name, api_key) VALUES (?, ?, ?)",
        [
            ("store_a", "Toy Kingdom", "key-store-a-123"),
            ("store_b", "Sneaker World", "key-store-b-456"),
        ],
    )

  # Create the multi-tenant sales table with a composite index on tenant_id and CustomerID
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
  cursor.execute(
      "CREATE INDEX IF NOT EXISTS idx_sales_tenant ON sales(tenant_id, CustomerID);"
  )

  # Seed starter sales for Store A and Store B if the sales table is empty
  cursor.execute("SELECT COUNT(*) FROM sales")
  if cursor.fetchone()[0] == 0:
    sample_sales = [
        ("store_a", "536365", "Priya", "2026-10-30", 20, 100.0),
        ("store_a", "536366", "Priya", "2026-10-27", 15, 80.0),
        ("store_a", "536367", "Alice", "2026-10-29", 10, 50.0),
        ("store_a", "536368", "Bob", "2026-09-10", 2, 30.0),
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

  # Save all changes and close the database connection
  conn.commit()
  conn.close()