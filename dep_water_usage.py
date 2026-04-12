"""
NYC DEP Daily Water Usage Emailer
----------------------------------
Logs into the DEP portal, fetches your latest billed water usage,
and emails it to you via Gmail SMTP.

Setup:
  1. pip install playwright python-dotenv requests
  2. playwright install chromium
  3. Copy .env.example to .env and fill in your values
  4. python dep_water_usage.py
"""

import os
import json
import smtplib
import requests
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import quote

load_dotenv()

# --- Config (loaded from .env) ---
DEP_USERNAME   = os.getenv("DEP_USERNAME")       # Your DEP portal email
DEP_PASSWORD   = os.getenv("DEP_PASSWORD")       # Your DEP portal password
ACCOUNT_ID     = os.getenv("DEP_ACCOUNT_ID")     # e.g. 0000553243
SERVICE_ID     = os.getenv("DEP_SERVICE_ID")     # e.g. S0003xy317960
METER_ID      = os.getenv("DEP_METER_ID")      # e.g. M0001xy97578
REGISTER_ID   = os.getenv("DEP_REGISTER_ID")   # e.g. R000013968
GMAIL_ADDRESS  = os.getenv("GMAIL_ADDRESS")      # Your Gmail address
GMAIL_APP_PW   = os.getenv("GMAIL_APP_PASSWORD") # Gmail App Password (not your real password)
EMAIL_TO       = os.getenv("EMAIL_TO")           # Where to send the report (can be same as GMAIL_ADDRESS)
HEADLESS        = os.getenv("HEADLESS", "false").lower() == "true"

# --- DEP API URLs ---
DEP_LOGIN_URL  = "https://a826-umax.dep.nyc.gov/"
GET_TOKEN_URL  = "https://a826-umax.dep.nyc.gov/Session/GetAuthTokenForCurrentUser"


def build_usage_url() -> str:
    today = datetime.now().strftime("%a %b %d %Y")  # e.g. "Sat Apr 11 2026"
    encoded_date = quote(today)                      # e.g. "Sat%20Apr%2011%202026"
    return (
        "https://umaxazprodcsswebapin.azurewebsites.net/api/account/GetExtendedDailyUsageGraphData"
        f"?accountId={ACCOUNT_ID}"
        f"&serviceId={SERVICE_ID}"
        f"&meterId={METER_ID}"
        f"&graphTypeId=DailyMonth"
        f"&periodFromDate={encoded_date}"
        f"&periodToDate=null"
        f"&includeWeatherOverlay=false"
        f"&registerId={REGISTER_ID}"
        f"&compareRange=None"
    )



def login_and_get_session_cookie() -> str:
    """
    Opens a visible browser, logs into the DEP portal,
    and returns the .AspNetCore.Cookies session cookie value.
    """
    print(">>> Launching browser and logging in...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to DEP portal — this will redirect to B2C login
        page.goto(DEP_LOGIN_URL, wait_until="networkidle")

        # Fill in credentials
        # NOTE: If the selectors below don't match, open DevTools on the login
        # page, inspect the username/password fields, and update accordingly.
        print(">>> Filling in credentials...")
        page.fill('#signInName', DEP_USERNAME)
        page.fill('#password', DEP_PASSWORD)

        # Click the sign-in button
        page.click('button[id="next"]')

        # Wait for redirect back to DEP portal
        print(">>> Waiting for login redirect...")
        page.wait_for_url("**/a826-umax.dep.nyc.gov/**", timeout=30000)
        page.wait_for_load_state("networkidle")

        # Extract the session cookie
        cookies = context.cookies()
        session_cookie = next(
            (c for c in cookies if c["name"] == ".AspNetCore.Cookies"), None
        )

        browser.close()

        if not session_cookie:
            raise RuntimeError(
                "Could not find .AspNetCore.Cookies after login. "
                "Check that login succeeded and inspect the browser for errors."
            )

        print(">>> Session cookie obtained.")
        return session_cookie["value"]


def get_bearer_token(session_cookie_value: str) -> str:
    """
    Calls the DEP token endpoint using the session cookie
    and returns the Bearer JWT string.
    """
    print(">>> Fetching Bearer token...")
    resp = requests.get(
        GET_TOKEN_URL,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://a826-umax.dep.nyc.gov/",
        },
        cookies={".AspNetCore.Cookies": session_cookie_value},
    )
    resp.raise_for_status()

    data = resp.json()

    # Print the full response so you can confirm the token field name on first run:
    print(f">>> GetAuthTokenForCurrentUser response: {json.dumps(data, indent=2)}")

    token = data

    print(">>> Bearer token obtained.")
    return token


def get_usage_data(bearer_token: str) -> dict:
    """
    Calls the usage API and returns the parsed JSON response.
    """
    print(">>> Fetching water usage data...")
    url = build_usage_url()
    resp = requests.get(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Authorization": f"Bearer {bearer_token}",
            "Origin": "https://a826-umax.dep.nyc.gov",
            "Referer": "https://a826-umax.dep.nyc.gov/",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    # Print raw response on first run so you can see the structure:
    print(f">>> Usage API response (truncated):\n{json.dumps(data, indent=2)[:1500]}")
    return data


def extract_latest_usage(data: dict) -> tuple:
    """
    Extracts the most recent day with an actual reading (isNoRead=False)
    from the consumption list.
    """
    consumption = data.get("consumption", [])

    # Filter to only days with actual readings
    actual_readings = [c for c in consumption if not c["isNoRead"]]

    if not actual_readings:
        raise RuntimeError("No actual readings found in response.")

    latest = actual_readings[-1]

    date_str   = latest["timePeriod"]                          # e.g. "2026/04/11"
    cf         = latest["value"]                               # e.g. 32.0
    gallons    = cf * 7.48                                     # convert CF to gallons
    charge     = latest["approximateCharge"]                   # e.g. 3.56
    unit       = latest["consumptionUnitOfMeasureSymbol"]      # "CF"

    summary = (
        f"{cf:.1f} {unit} ({gallons:.0f} gallons) — approx. ${charge:.2f}"
    )

    return date_str, summary


def send_email(date_str: str, usage_str: str, monthly_summary: str) -> None:
    """
    Sends a Gmail email with the water usage summary.

    Gmail App Password setup:
      1. Enable 2-Step Verification on your Google account
      2. Go to myaccount.google.com > Security > App Passwords
      3. Create an App Password for "Mail"
      4. Paste the 16-character password as GMAIL_APP_PASSWORD in your .env
    """
    today = datetime.now().strftime("%B %d, %Y")
    subject = f"NYC DEP Water Usage — (Yesterdays reading: {usage_str})"
    body = (
        f"Your NYC DEP water usage report for yesterday\n\n"
        f"  Latest reading:  {date_str}\n"
        f"  Usage:           {usage_str}\n\n"
        f"  For comparison, the highest single day reading this year has been: 225 CF on January 22.\n"
        f"  Month to date:   {monthly_summary}\n\n"
        f"View full details at: https://a826-umax.dep.nyc.gov/\n"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = EMAIL_TO

    print(f">>> Sending email to {EMAIL_TO}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PW)
        server.sendmail(GMAIL_ADDRESS, EMAIL_TO, msg.as_string())
    print(">>> Email sent successfully.")


def main():
    try:
        session_cookie          = login_and_get_session_cookie()
        bearer_token            = get_bearer_token(session_cookie)
        usage_data              = get_usage_data(bearer_token)
        date_str, usage_str     = extract_latest_usage(usage_data)
        monthly_summary         = usage_data["summary"][0]  # "Your total consumption = 359.00 CF"



        print(f"\n=== Latest Usage: {usage_str} on {date_str} ===\n")
        send_email(date_str, usage_str, monthly_summary)

    except PlaywrightTimeoutError:
        print("ERROR: Timed out waiting for login. Check your credentials or the login page selectors.")
    except requests.HTTPError as e:
        print(f"ERROR: API call failed — {e}")
    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()