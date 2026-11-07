import os
import sqlite3

# Store the database inside the fast native Linux volume (/app/data) if set, else local folder
BASE_DIR = os.getenv("DB_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "ecommerce.db")


# Initializes the database schema, adds the Product column, and indexes for fast queries
def init_db():
  conn = sqlite3.connect(DB_PATH, timeout=60)
  cursor = conn.cursor()

  # Enable Write-Ahead Logging (WAL) for high-speed concurrent reads and million-row writes
  cursor.execute("PRAGMA journal_mode=WAL;")
  cursor.execute("PRAGMA synchronous=NORMAL;")

  # Create the stores table to persist every uploaded dataset file and its upload timestamp
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            tenant_id TEXT PRIMARY KEY,
            store_name TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

  # Safely add created_at column if upgrading from an older stores table
  try:
    cursor.execute("ALTER TABLE stores ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
  except sqlite3.OperationalError:
    pass

  # Create the sales table with a nullable Profit column (NULL when dataset lacks profit/cost data)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            InvoiceNo TEXT NOT NULL,
            CustomerID TEXT NOT NULL,
            InvoiceDate TEXT NOT NULL,
            Product TEXT DEFAULT 'General Item',
            Quantity INTEGER NOT NULL,
            UnitPrice REAL NOT NULL,
            Profit REAL DEFAULT NULL
        )
    """)

  # Safely migrate existing databases by adding Product and nullable Profit columns
  for col_sql in [
      "ALTER TABLE sales ADD COLUMN Product TEXT DEFAULT 'General Item';",
      "ALTER TABLE sales ADD COLUMN Profit REAL DEFAULT NULL;",
  ]:
    try:
      cursor.execute(col_sql)
    except sqlite3.OperationalError:
      pass

  # Create composite indexes on tenant_id, CustomerID, and Product for fast search and grouping
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_tenant ON sales(tenant_id, CustomerID);")
  cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(tenant_id, Product);")

  # Seed one starter dataset only if the database has zero datasets uploaded yet
  cursor.execute("SELECT COUNT(*) FROM stores")
  if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO stores (tenant_id, store_name, api_key) VALUES (?, ?, ?)",
        ("dataset_sample_sales", "sample_sales.csv", "key-sample-sales"),
    )
    sample_sales = [
        ("dataset_sample_sales", "536365", "Priya", "2026-08-15", "Wireless Mouse", 20, 100.0),
        ("dataset_sample_sales", "536366", "Priya", "2026-09-20", "Mechanical Keyboard", 15, 80.0),
        ("dataset_sample_sales", "536367", "Alice", "2026-10-10", "Wireless Mouse", 10, 50.0),
        ("dataset_sample_sales", "536368", "Bob", "2026-10-25", "USB-C Hub", 2, 30.0),
    ]
    cursor.executemany(
        """
            INSERT INTO sales (tenant_id, InvoiceNo, CustomerID, InvoiceDate, Product, Quantity, UnitPrice)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        sample_sales,
    )

  # Commit schema updates and close the connection
  conn.commit()
  conn.close()