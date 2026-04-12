# NYC DEP Water Usage Emailer

A Python script that automatically logs into the NYC Department of Environmental Protection (DEP) portal, fetches your latest daily water usage data, and emails you a summary report via Gmail.

## Features

- Automated login to NYC DEP portal using Playwright browser automation
- Fetches real-time water usage data from DEP's API
- Converts cubic feet (CF) to gallons for easier understanding
- Sends formatted email reports with usage summaries
- Includes month-to-date consumption totals
- Configurable headless/browser mode for debugging

## Prerequisites

- Python 3.13 or higher
- A Gmail account with 2-Step Verification enabled (for App Password)
- Access to NYC DEP water account portal

## Installation

1. Clone or download this repository
2. Install dependencies using uv (recommended):

```bash
uv sync
```

Or using pip:

```bash
pip install playwright python-dotenv requests
```

3. Install Playwright browsers:

```bash
playwright install chromium
```

## Configuration

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Fill in your credentials in `.env`:

```env
# DEP Portal Credentials
DEP_USERNAME=your_dep_email@example.com
DEP_PASSWORD=your_dep_password
ACCOUNT_ID=0000553243
SERVICE_ID=S0003xy317960
METER_ID=M0001xy97578
REGISTER_ID=R000013968

# Gmail Settings
GMAIL_ADDRESS=your_gmail@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
EMAIL_TO=recipient@example.com

# Optional: Set to 'true' to run browser in headless mode
HEADLESS=false
```

### Getting Your DEP Account Details

1. Log into the DEP portal at https://a826-umax.dep.nyc.gov/
2. Navigate to your account details
3. Find your Account ID, Service ID, Meter ID, and Register ID
4. These are typically visible in the URL or account information section

### Setting Up Gmail App Password

1. Enable 2-Step Verification on your Google account
2. Go to [Google Account Settings > Security > App Passwords](https://myaccount.google.com/apppasswords)
3. Generate an App Password for "Mail"
4. Use the 16-character password (not your regular password) in `GMAIL_APP_PASSWORD`

## Usage

Run the script:

```bash
uv run dep_water_usage.py
```

Or if using pip:

```bash
python dep_water_usage.py
```

The script will:
1. Launch a browser and log into DEP
2. Fetch your latest water usage data
3. Send an email with the usage summary

## How It Works

1. **Browser Automation**: Uses Playwright to automate login to the DEP portal
2. **Session Management**: Extracts session cookies after successful login
3. **API Authentication**: Obtains a Bearer token for API access
4. **Data Retrieval**: Calls DEP's usage API to get daily consumption data
5. **Data Processing**: Extracts the latest reading and calculates gallons from cubic feet
6. **Email Delivery**: Sends a formatted report via Gmail SMTP

## Security Notes

- Store your `.env` file securely and never commit it to version control
- The script requires your DEP portal credentials - keep them confidential
- Gmail App Passwords are specific to this application and can be revoked if needed
- The browser automation is visible by default for transparency (set `HEADLESS=true` to hide it)

## Troubleshooting

- **Login fails**: Check your DEP credentials and ensure the portal is accessible
- **Email not sent**: Verify Gmail App Password and 2-Step Verification setup
- **API errors**: DEP may have changed their API - check the printed responses for clues
- **Browser issues**: Try running with `HEADLESS=false` to see what's happening

## License

MIT License - see LICENSE file for details (if applicable)