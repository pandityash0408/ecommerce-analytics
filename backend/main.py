import os
from fastapi import FastAPI
import pandas as pd

app = FastAPI()

# Always find sales.csv right next to main.py inside the backend folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "sales.csv")


@app.get("/hello")
def say_hello():
  return {"message": "Hello from the kitchen!"}


@app.get("/rfm")
def get_rfm():
  # 1. Read the sales file right inside backend/
  df = pd.read_csv(CSV_PATH)

  # Clean column names just in case there are extra spaces
  df.columns = df.columns.str.strip()

  # 2. Calculate total price for each row (Quantity * UnitPrice)
  df["TotalPrice"] = df["Quantity"] * df["UnitPrice"]

  # 3. Turn InvoiceDate into real calendar dates
  df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

  # 4. Pick "today" as 1 day after the latest purchase in the file
  today = df["InvoiceDate"].max() + pd.Timedelta(days=1)

  # 5. Group by CustomerID to calculate Recency, Frequency, and Monetary
  rfm = (
      df.groupby("CustomerID")
      .agg(
          Recency=("InvoiceDate", lambda dates: int((today - dates.max()).days)),
          Frequency=("InvoiceNo", lambda x: int(x.nunique())),
          Monetary=("TotalPrice", lambda x: float(x.sum())),
      )
      .reset_index()
  )

  # 6. Sort from biggest spender (Best Customer) to smallest
  rfm = rfm.sort_values(by="Monetary", ascending=False)

  # 7. Send the table back as a list of dictionaries
  return rfm.to_dict(orient="records")

