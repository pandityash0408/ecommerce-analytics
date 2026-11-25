# Automated Selenium End-to-End UI Test Suite (Login Gate + Dashboard + Charts + Inspector)
import os
import time
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

BASE_URL = os.getenv("DASHBOARD_URL", "http://localhost:3000")


# Launches headless Chrome (falls back to Microsoft Edge on Windows automatically)
@pytest.fixture(scope="module")
def driver():
  browser = None
  try:
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--ignore-certificate-errors")
    browser = webdriver.Chrome(options=opts)
  except Exception:
    opts = webdriver.EdgeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--ignore-certificate-errors")
    browser = webdriver.Edge(options=opts)
  browser.implicitly_wait(5)
  yield browser
  browser.quit()


# 1. Verify unauthenticated user is redirected to /login and can sign in cleanly
def test_login_gate_and_authentication(driver):
  driver.get(BASE_URL)
  wait = WebDriverWait(driver, 15)
  wait.until(lambda d: "/login" in d.current_url or "Sign In" in d.title)
  assert "Sign In" in driver.title

  driver.find_element(By.ID, "username").send_keys("yash")
  driver.find_element(By.ID, "password").send_keys("Yash@2026")
  driver.find_element(By.ID, "submitBtn").click()

  wait.until(lambda d: "Customer Behavior" in d.title)
  assert "Customer Behavior" in driver.title


# 2. Verify dashboard loads with non-zero KPI cards after login
def test_dashboard_loads_and_shows_kpis(driver):
  wait = WebDriverWait(driver, 15)
  wait.until(lambda d: d.find_element(By.ID, "activeFileName").text.strip() not in ("", "Loading dataset..."))

  rev_text = driver.find_element(By.ID, "kpiRevenue").text
  cust_text = driver.find_element(By.ID, "kpiCustomers").text
  assert rev_text.startswith("₹")
  assert cust_text != "0"


# 3. Verify left dataset sidebar populates automatically on startup
def test_sidebar_datasets_populated(driver):
  count_val = int(driver.find_element(By.ID, "datasetCount").text.strip() or "0")
  assert count_val >= 1


# 4. Verify switching Line Chart -> Bar Graph -> Map Graph works with zero blank states
def test_chart_style_switching_line_bar_map(driver):
  style_select = Select(driver.find_element(By.ID, "chartStyleSelect"))

  style_select.select_by_value("bar")
  time.sleep(1)
  assert driver.find_element(By.ID, "productTrendChart").is_displayed()

  style_select.select_by_value("map")
  time.sleep(1)
  map_div = driver.find_element(By.ID, "productGeoMap")
  notice_div = driver.find_element(By.ID, "mapNotice")
  assert map_div.is_displayed() or notice_div.is_displayed()

  style_select.select_by_value("line")
  time.sleep(1)
  assert driver.find_element(By.ID, "productTrendChart").is_displayed()


# 5. Verify switching Month-wise -> Year-wise keeps From/To date dropdowns populated
def test_granularity_month_to_year_keeps_date_range(driver):
  gran_select = Select(driver.find_element(By.ID, "trendGranularity"))
  gran_select.select_by_value("year")
  time.sleep(1.5)

  start_opts = Select(driver.find_element(By.ID, "startPeriodSelect")).options
  end_opts = Select(driver.find_element(By.ID, "endPeriodSelect")).options
  assert len(start_opts) >= 1
  assert len(end_opts) >= 1

  gran_select.select_by_value("month")
  time.sleep(1)


# 6. Verify Customer Segmentation Ledger & Account Inspector interaction
def test_customer_table_and_inspector(driver):
  rows = driver.find_elements(By.CSS_SELECTOR, "#customerTableBody tr")
  assert len(rows) >= 1
  rows[0].click()
  time.sleep(1)
  inspector_title = driver.find_element(By.ID, "c360Name").text
  assert inspector_title != "Select a customer"