import streamlit as st
import time
import random
import requests
from datetime import datetime, timedelta
import statistics
from dateutil import parser
from bs4 import BeautifulSoup  # Import BeautifulSoup for HTML parsing

# Browserless API setup
API_URL = "https://browserless.io/webdriver"
API_KEY = "S3T6z4PxrpL5U5862f350c798784656b9eedb3af1f"

# Function to start a Browserless session
def start_browser_session():
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "url": "https://sectbot.com",  # Starting page (can be adjusted)
        "waitFor": "document.readyState=='complete'"
    }
    response = requests.post(f"{API_URL}/launch", headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()['session']
    else:
        st.error("Failed to start Browserless session.")
        return None

# Function to end the Browserless session
def end_browser_session(session_id):
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "session": session_id
    }
    requests.post(f"{API_URL}/close", headers=headers, json=payload)

# Function to scrape the page and get stats
def get_caller_stats(session_id, name, mode, custom_val=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    url = f"https://sectbot.com/caller/{name}"
    
    # Interact with the browserless API to go to the page and extract the content
    payload = {
        "session": session_id,
        "url": url,
        "script": "return document.body.innerHTML;"  # Scraping the page content
    }
    page_content_response = requests.post(f"{API_URL}/execute", headers=headers, json=payload)
    
    if page_content_response.status_code != 200:
        st.error(f"Failed to retrieve page content for {name}.")
        return
    
    page_content = page_content_response.json()['value']
    
    # Parse the page content using BeautifulSoup
    soup = BeautifulSoup(page_content, "html.parser")
    
    # Extract trade data
    trades = []
    trade_elements = soup.find_all("div", class_="call-box")
    
    for el in trade_elements:
        try:
            token = el.find("h3").get_text()  # Example: Adjust based on the HTML structure
            timestamp = el.find("span", class_="timestamp").get_text()  # Adjust as needed
            called = float(el.find("span", class_="called").get_text())  # Adjust as needed
            reached = float(el.find("span", class_="reached").get_text())  # Adjust as needed
            dt = parser.parse(timestamp)
            mult = reached / called if called > 0 else 0
            trades.append({"token": token, "timestamp": dt, "multiplier": mult})
        except:
            continue
    
    # Now summarize the trades based on the mode
    t, a, w, m = summarize_trades(trades)
    
    st.subheader(f"{name} | Stats for {mode}")
    st.write(f"📈 Trades: {t}")
    st.write(f"💰 Avg: {a:.2f}x")
    st.write(f"🔺 Median: {m:.2f}x")
    st.write(f"✅ Winrate: {w:.1f}%")

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

# Main script with Streamlit
def main():
    st.title("SECTbot Caller Stats")
    
    session_id = start_browser_session()  # Start the Browserless session
    if not session_id:
        return
    
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

        get_caller_stats(session_id, caller, mode, value)
    
    # End the session after use
    end_browser_session(session_id)

if __name__ == "__main__":
    main()
