import requests
import streamlit as st

st.title("My E-Commerce Store Dashboard")

if st.button("Call the Kitchen"):
  response = requests.get("http://127.0.0.1:8000/hello")
  data = response.json()
  st.success(data["message"])
  
