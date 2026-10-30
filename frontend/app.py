import pandas as pd
import requests
import streamlit as st

st.title("🛒 My E-Commerce Store Dashboard")

if st.button("Call the Kitchen"):
  response = requests.get("http://127.0.0.1:8000/hello")
  data = response.json()
  st.success(data["message"])

st.subheader("🏆 Best Customers (RFM Analysis)")

if st.button("Load Best Customers (RFM)"):
  # 1. Ask the waiter for the /rfm data from the kitchen
  response = requests.get("http://127.0.0.1:8000/rfm")
  rfm_data = response.json()

  # 2. Turn the data into a clean table
  df = pd.DataFrame(rfm_data)

  # 3. Show the table on screen
  st.write("Here are your customers ranked by total money spent:")
  st.dataframe(df, use_container_width=True)

  # 4. Draw a Bar Chart of Monetary value (Total Spent) per Customer
  st.write("### 💰 Total Money Spent by Each Customer")
  st.bar_chart(df.set_index("CustomerID")["Monetary"])

  