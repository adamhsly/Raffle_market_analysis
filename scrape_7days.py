import os
import json
import requests
import pandas as pd
import gspread

from datetime import datetime
from google.oauth2.service_account import Credentials


URL = "https://7daysperformance.co.uk/api/v2/raffle-draws/GBP"

SHEET_NAME = "Raffle Tracker"
TAB_NAME = "7Days"


def fetch_7days():
    params = {
        "category[]": "current-competitions",
        "campaign": "null",
        "limit": 24,
        "offset": 0,
        "include_finished": "false",
        "include_running": "true",
        "include_soldout": "true",
        "sortby": "date",
        "filter": ""
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    response = requests.get(URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def transform(data):
    rows = []

    for item in data:
        offer = item.get("offers", [{}])[0] if item.get("offers") else {}

        current_entries = item.get("current_entries") or 0
        max_entries = item.get("max_entries") or 0
        price = float(offer.get("price") or 0)

        sold_percent = round((current_entries / max_entries) * 100, 2) if max_entries else ""
        revenue_to_date = round(current_entries * price, 2)

        rows.append({
            "scraped_at": datetime.utcnow().isoformat(timespec="seconds"),
            "site": "7Days Performance",
            "id": item.get("id"),
            "slug": item.get("slug"),
            "draw_name": item.get("title"),
            "subtitle": item.get("subtitle"),
            "ticket_price": price,
            "currency": offer.get("currency"),
            "start_at": item.get("start_at"),
            "end_at": item.get("end_at"),
            "result_at": item.get("result_at"),
            "prize_value": item.get("prize_value"),
            "cash_alternative": item.get("cash_alternative"),
            "current_entries": current_entries,
            "max_entries": max_entries,
            "sold_percent": sold_percent,
            "revenue_to_date": revenue_to_date,
            "is_cash": item.get("is_cash"),
            "is_open": item.get("is_open"),
            "draw_method": item.get("draw_method"),
            "instant_win_count": item.get("instant_win_count"),
            "prize_count": item.get("prize_count"),
            "default_tickets": item.get("default_tickets"),
            "ticket_limit_per_user": item.get("ticket_limit_per_user"),
            "category_ids": ", ".join(item.get("category_ids", [])),
            "thumbnail_url": item.get("thumbnail", {}).get("url"),
            "competition_url": f"https://7daysperformance.co.uk/competitions/{item.get('slug')}"
        })

    return pd.DataFrame(rows)


def save_to_google_sheet(df):
    service_account_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(service_account_json)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open(SHEET_NAME)

    existing_tabs = [ws.title for ws in sh.worksheets()]

    if TAB_NAME in existing_tabs:
        worksheet = sh.worksheet(TAB_NAME)
    else:
        worksheet = sh.add_worksheet(title=TAB_NAME, rows=1000, cols=50)

    worksheet.clear()

    df = df.replace([float("inf"), float("-inf")], "")
    df = df.where(pd.notnull(df), "")
    df = df.astype(str)

    values = [df.columns.tolist()] + df.values.tolist()

    worksheet.update(values)


def main():
    data = fetch_7days()
    df = transform(data)

    if df.empty:
        raise Exception("No competitions found from 7Days API")

    save_to_google_sheet(df)

    print(f"Saved {len(df)} competitions to Google Sheets")


if __name__ == "__main__":
    main()
