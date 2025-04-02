import streamlit as st
import time
import random
import os
import sys
from datetime import datetime, timedelta
import statistics
from dateutil import parser
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Click "Show more" until enough trades are loaded
def click_show_more_until(driver, mode="days", value=None):
    last_count = 0
    click_attempts = 0
    while True:
        try:
            trades = driver.find_elements(By.CLASS_NAME, "call-box")
            if not trades:
                break

            if mode == "calls" and len(trades) >= value:
                break
            elif mode == "days" and value is not None:
                last_trade_text = trades[-1].text.split("\n")
                last_timestamp = last_trade_text[1]
                last_date = parser.parse(last_timestamp)
                if last_date < datetime.now() - timedelta(days=value):
                    break
            elif mode == "24h":
                last_trade_text = trades[-1].text.split("\n")
                last_timestamp = last_trade_text[1]
                last_date = parser.parse(last_timestamp)
                if last_date < datetime.now() - timedelta(days=1):
                    break

            if len(trades) == last_count:
                break
            last_count = len(trades)

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.4)

            show_more = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "body > div.relative.mb-16.flex.min-h-screen.flex-col.items-center.justify-center.bg-black.px-4.md\\:px-6.xl\\:px-16 > div.z-40.flex.w-full.flex-col.items-center > div > div.card-container.relative.w-full.overflow-hidden.rounded-lg.border-2.border-\\[\\#0c5138\\].bg-sect-dark\\/80.shadow-lg > div > div.px-8 > p"))
            )
            show_more.click()
            click_attempts += 1
            time.sleep(1.0)

        except Exception:
            break

    # Removed the st.info line here
    # st.info(f"Clicked 'Show more' {click_attempts} times.")  # <-- Removed

# Convert shorthand values like 5.6K, 3.2M, etc.
def convert(val):
    val = val.upper().replace(",", "")
    if "K" in val:
        return float(val.replace("K", "")) * 1_000
    elif "M" in val:
        return float(val.replace("M", "")) * 1_000_000
    elif "B" in val:
        return float(val.replace("B", "")) * 1_000_000_000
    else:
        return float(val)

# Extract trade blocks from the page
def parse_recent_trades(driver):
    trade_elements = driver.find_elements(By.CLASS_NAME, "call-box")
    trades = []
    for el in trade_elements:
        try:
            text = el.text.split("\n")
            token = text[0]
            timestamp = text[1]
            called = convert(text[text.index("Called at") + 1])
            reached = convert(text[text.index("Reached") + 1])
            dt = parser.parse(timestamp)
            mult = reached / called if called > 0 else 0
            trades.append({"token": token, "timestamp": dt, "multiplier": mult})
        except:
            continue
    return trades

# Summarize trade performance over given period
def summarize_trades(trades):
    total = len(trades)
    if total == 0:
        return (0, 0, 0, 0)
    multipliers = [t['multiplier'] for t in trades]
    avg_x = sum(multipliers) / total
    median_x = statistics.median(multipliers)
    wins = sum(1 for m in multipliers if m >= 2.0)
    winrate = (wins / total) * 100
    return (total, avg_x, winrate, median_x)

# Extract stats from caller page
def get_caller_stats(driver, name, mode, custom_val=None):
    url = f"https://sectbot.com/caller/{name}"
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Winrate')]/following-sibling::div"))
        )
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(0.5)
        click_show_more_until(driver, mode, custom_val)
        trades = parse_recent_trades(driver)

        if mode == "calls":
            trades = trades[:custom_val]
            t, a, w, m = summarize_trades(trades)
            st.subheader(f"{name} | Last {custom_val} calls")
            st.write(f"📈 Trades: {t}")
            st.write(f"💰 Avg: {a:.2f}x")
            st.write(f"🔺 Median: {m:.2f}x")
            st.write(f"✅ Winrate: {w:.1f}%")

        elif mode == "days":
            t_custom = [t for t in trades if t['timestamp'] >= datetime.now() - timedelta(days=custom_val)]
            t, a, w, m = summarize_trades(t_custom)
            st.subheader(f"{name} | Last {custom_val} Days")
            st.write(f"📅 Trades: {t}")
            st.write(f"💰 Avg: {a:.2f}x")
            st.write(f"🔺 Median: {m:.2f}x")
            st.write(f"✅ Winrate: {w:.1f}%")

        elif mode == "24h":
            recent = [t for t in trades if t['timestamp'] >= datetime.now() - timedelta(days=1)]
            t, a, w, m = summarize_trades(recent)
            st.subheader(f"{name} | Last 24 Hours")
            st.write(f"⏰ Trades: {t}")
            st.write(f"💰 Avg: {a:.2f}x")
            st.write(f"🔺 Median: {m:.2f}x")
            st.write(f"✅ Winrate: {w:.1f}%")

    except Exception as e:
        st.error(f"Scraping failed for {name}: {e}")

# Setup Selenium WebDriver
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Use headless mode for deployment
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument(f"--user-agent={random_user_agent()}")

    # Specify the path to chromedriver if it's in the same directory as your script
    service = Service(executable_path=os.path.join(os.getcwd(), "chromedriver.exe"))
    return webdriver.Chrome(service=service, options=chrome_options)

def random_user_agent():
    return random.choice([ 
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36", 
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36", 
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36", 
    ])

# Main script with Streamlit
def main():
    st.title("SECTbot Caller Stats")
    
    driver = setup_driver()
    
    caller = st.text_input("Enter caller username:")
    mode_choice = st.selectbox("Choose mode:", [
        "Last 20 calls", "Last 24 hours", "Custom Time Range (in days)", "Custom Number of Calls"
    ])
    
    if mode_choice == "Custom Time Range (in days)":
        custom_days = st.number_input("Custom day range (e.g. 4):", min_value=1, value=7)
    elif mode_choice == "Custom Number of Calls":
        custom_calls = st.number_input("Custom number of calls (e.g. 50):", min_value=1, value=20)

    if st.button("Get Stats"):
        if mode_choice == "Last 20 calls":
            mode = "calls"
            value = 20
        elif mode_choice == "Last 24 hours":
            mode = "24h"
            value = None
        elif mode_choice == "Custom Time Range (in days)":
            mode = "days"
            value = custom_days
        elif mode_choice == "Custom Number of Calls":
            mode = "calls"
            value = custom_calls

        get_caller_stats(driver, caller, mode, value)

if __name__ == "__main__":
    main()
