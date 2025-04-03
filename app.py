import streamlit as st
import time
import random
import os
from datetime import datetime, timedelta
import statistics
from dateutil import parser
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
# Removed chromedriver_autoinstaller import

# -----------------------------
# Your Functions
# -----------------------------

def click_show_more_until(driver, mode="days", value=None, max_attempts=30):
    st.write("Loading Data...")
    attempts = 0
    prev_count = 0
    show_more_selector = (
        "body > div.relative.mb-16.flex.min-h-screen.flex-col.items-center.justify-center.bg-black.px-4.md\\:px-6.xl\\:px-16 > "
        "div.z-40.flex.w-full.flex-col.items-center > div > "
        "div.card-container.relative.w-full.overflow-hidden.rounded-lg.border-2.border-\\[\\#0c5138\\].bg-sect-dark\\/80.shadow-lg > "
        "div > div.px-8 > p"
    )
    while attempts < max_attempts:
        trades = driver.find_elements(By.CLASS_NAME, "call-box")
        if mode == "calls" and len(trades) >= (value or 0):
            break
        if mode in ["days", "24h"] and value is not None and trades:
            last_trade_text = trades[-1].text.split("\n")
            if len(last_trade_text) >= 2:
                last_timestamp = last_trade_text[1]
                last_date = parser.parse(last_timestamp)
                if mode == "days" and last_date < datetime.now() - timedelta(days=value):
                    break
                elif mode == "24h" and last_date < datetime.now() - timedelta(days=1):
                    break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        try:
            show_more = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, show_more_selector))
            )
            if "show more" in show_more.text.lower():
                driver.execute_script("arguments[0].click();", show_more)
                time.sleep(2)
            else:
                break
        except Exception as e:
            break
        new_count = len(driver.find_elements(By.CLASS_NAME, "call-box"))
        if new_count <= prev_count:
            break
        prev_count = new_count
        attempts += 1

def convert(val):
    val = val.upper().replace(",", "")
    if "K" in val:
        return float(val.replace("K", "")) * 1_000
    elif "M" in val:
        return float(val.replace("M", "")) * 1_000_000
    elif "B" in val:
        return float(val.replace("B", "")) * 1_000_000_000
    else:
        try:
            return float(val)
        except:
            return 0.0

def parse_recent_trades(driver):
    trade_elements = driver.find_elements(By.CLASS_NAME, "call-box")
    trades = []
    for el in trade_elements:
        try:
            text = el.text.split("\n")
            if len(text) < 4:
                continue
            token = text[0]
            timestamp = text[1]
            if "Called at" in text and "Reached" in text:
                c_idx = text.index("Called at") + 1
                r_idx = text.index("Reached") + 1
                called = convert(text[c_idx])
                reached = convert(text[r_idx])
                dt = parser.parse(timestamp)
                mult = reached / called if called > 0 else 0
                trades.append({"token": token, "timestamp": dt, "multiplier": mult})
        except Exception:
            continue
    return trades

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

def get_caller_stats(driver, name, mode, custom_val=None, print_summary=True):
    url = f"https://sectbot.com/caller/{name}"
    driver.get(url)
    trades = []
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "call-box"))
        )
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(1)
        click_show_more_until(driver, mode, custom_val)
        trades = parse_recent_trades(driver)
        if mode == "calls" and print_summary:
            trades = trades[:custom_val]
            t, a, w, m = summarize_trades(trades)
            st.markdown(f"**{name} | Last {custom_val} calls**")
            st.write("────────────────────────────────────────")
            st.write(f"📈 Trades: {t}  \n💰 Avg: {a:.2f}x  \n🔺 Median: {m:.2f}x  \n✅ Winrate: {w:.1f}%")
            st.write("────────────────────────────────────────")
    except Exception as e:
        st.error(f"Scraping failed for {name}: {e}")
    return trades

def calculate_tps(trades):
    """
    For each TP threshold (from 1.6x to 2.8x), compute:
      - Hit Rate: % of trades where multiplier >= TP.
    """
    tp_ranges = [round(x * 0.1, 1) for x in range(16, 29)]
    total_trades = len(trades)
    tp_stats = {}
    for tp in tp_ranges:
        wins = sum(1 for t in trades if t['multiplier'] >= tp)
        tp_stats[tp] = (wins / total_trades) * 100 if total_trades > 0 else 0.0
    return tp_stats

def calculate_expected_returns(trades):
    """
    For each TP threshold, compute the expected return per $100 trade:
      Expected Return = 100 × ((hit_rate/100) × TP – (1 - hit_rate/100))
    """
    tp_stats = calculate_tps(trades)
    expected_returns = {}
    for tp, hit_rate in tp_stats.items():
        p = hit_rate / 100
        expected_returns[tp] = 100 * (p * tp - (1 - p))
    return expected_returns

def best_tps(trades, top_n=3):
    expected_returns = calculate_expected_returns(trades)
    best = sorted(expected_returns.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return best

def setup_driver():
    # Remove chromedriver_autoinstaller.install() if present
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Set binary location to the typical path for Chromium on Streamlit Cloud (Debian-based)
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    chrome_options.add_argument(f"--user-agent={random_user_agent()}")
    service = Service(executable_path="./chromedriver")
    return webdriver.Chrome(service=service, options=chrome_options)

def random_user_agent():
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    ])

# -----------------------------
# Streamlit App UI
# -----------------------------

st.title("SectBot Caller Stats")

caller = st.text_input("Enter caller username:")
mode_option = st.selectbox("Select Mode:", ("Custom Time Range (in days)", "Custom Number of Calls", "TP Calculation"))

if caller:
    if mode_option == "Custom Time Range (in days)":
        days = st.number_input("Enter number of days", min_value=1, value=4, step=1)
        with st.spinner("Fetching stats..."):
            driver = setup_driver()
            get_caller_stats(driver, caller, "days", int(days))
            driver.quit()
    elif mode_option == "Custom Number of Calls":
        num_calls = st.number_input("Enter number of calls", min_value=1, value=50, step=1)
        with st.spinner("Fetching stats..."):
            driver = setup_driver()
            get_caller_stats(driver, caller, "calls", int(num_calls))
            driver.quit()
    elif mode_option == "TP Calculation":
        with st.spinner("Fetching trades for TP Calculation..."):
            driver = setup_driver()
            trades_all = get_caller_stats(driver, caller, "calls", 50, print_summary=False)
            driver.quit()
        if not trades_all:
            st.error("No trades found for TP Calculation.")
        else:
            if len(trades_all) < 25:
                st.warning(f"Only {len(trades_all)} trades available. Using same dataset for both Last 25 and Last 50.")
                trades_25 = trades_all
                trades_50 = trades_all
            else:
                trades_25 = trades_all[:25]
                trades_50 = trades_all[:50]
            
            while True:
                st.markdown("**Choose TP Calculation Method:**")
                method_choice = st.radio("", ("Show TP thresholds with Hit Rate", "Show Best 3 TPs (based on Expected Return)", "Go back to Main Menu"))
                if method_choice == "Show TP thresholds with Hit Rate":
                    t25, a25, w25, m25 = summarize_trades(trades_25)
                    st.markdown(f"**{caller} | Last 25 calls**")
                    st.write("────────────────────────────────────────")
                    st.write(f"📈 Trades: {t25}  \n💰 Avg: {a25:.2f}x  \n🔺 Median: {m25:.2f}x  \n✅ Winrate: {w25:.1f}%")
                    st.write("────────────────────────────────────────")
                    st.write("--- TP Calculation for Last 25 Trades ---")
                    tp_stats_25 = calculate_tps(trades_25)
                    for tp in sorted(tp_stats_25.keys()):
                        st.write(f"TP: {tp}x | Hit Rate: {tp_stats_25[tp]:.1f}%")
                    
                    t50, a50, w50, m50 = summarize_trades(trades_50)
                    st.markdown(f"**{caller} | Last 50 calls**")
                    st.write("────────────────────────────────────────")
                    st.write(f"📈 Trades: {t50}  \n💰 Avg: {a50:.2f}x  \n🔺 Median: {m50:.2f}x  \n✅ Winrate: {w50:.1f}%")
                    st.write("────────────────────────────────────────")
                    st.write("--- TP Calculation for Last 50 Trades ---")
                    tp_stats_50 = calculate_tps(trades_50)
                    for tp in sorted(tp_stats_50.keys()):
                        st.write(f"TP: {tp}x | Hit Rate: {tp_stats_50[tp]:.1f}%")
                elif method_choice == "Show Best 3 TPs (based on Expected Return)":
                    expected_returns_25 = calculate_expected_returns(trades_25)
                    best_three_25 = sorted(expected_returns_25.items(), key=lambda x: x[1], reverse=True)[:3]
                    
                    expected_returns_50 = calculate_expected_returns(trades_50)
                    best_three_50 = sorted(expected_returns_50.items(), key=lambda x: x[1], reverse=True)[:3]
                    
                    t25, a25, w25, m25 = summarize_trades(trades_25)
                    st.markdown(f"**{caller} | Last 25 calls**")
                    st.write("────────────────────────────────────────")
                    st.write(f"📈 Trades: {t25}  \n💰 Avg: {a25:.2f}x  \n🔺 Median: {m25:.2f}x  \n✅ Winrate: {w25:.1f}%")
                    st.write("────────────────────────────────────────")
                    st.write("--- Best 3 TPs for Last 25 Trades ---")
                    for tp, er in best_three_25:
                        st.write(f"TP: {tp}x | Expected Return: ${er:.2f} per $100 trade")
                    
                    t50, a50, w50, m50 = summarize_trades(trades_50)
                    st.markdown(f"**{caller} | Last 50 calls**")
                    st.write("────────────────────────────────────────")
                    st.write(f"📈 Trades: {t50}  \n💰 Avg: {a50:.2f}x  \n🔺 Median: {m50:.2f}x  \n✅ Winrate: {w50:.1f}%")
                    st.write("────────────────────────────────────────")
                    st.write("--- Best 3 TPs for Last 50 Trades ---")
                    for tp, er in best_three_50:
                        st.write(f"TP: {tp}x | Expected Return: ${er:.2f} per $100 trade")
                elif method_choice == "Go back to Main Menu":
                    st.write("Returning to main menu.")
                    break
                else:
                    st.error("Invalid choice. Please select an option.")
