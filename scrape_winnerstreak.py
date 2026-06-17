import os
import json
import requests
import pandas as pd
import gspread

from datetime import datetime
from google.oauth2.service_account import Credentials


URL = "https://www.thewinnerstreak.com/api/raffles"
SHEET_NAME = "Raffle Tracker"
TAB_NAME = "WinnerStreak"


def fetch_winnerstreak():
    all_items = []
    page = 1
    per_page = 6

    while True:
        params = {
            "status": "live",
            "perPage": per_page,
            "orderBy": "end_date",
            "page": page
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }

        response = requests.get(URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        items = data.get("data", [])

        if not items:
            break

        all_items.extend(items)

        if len(items) < per_page:
            break

        page += 1

    return all_items


def first_value(item, keys, default=""):
    for key in keys:
        value = item.get(key)
        if value is not None:
            return value
    return default


def to_int(value):
    try:
        return int(float(value))
    except:
        return 0


def to_float(value):
    try:
        return float(value)
    except:
        return 0.0


def transform(data):
    rows = []

    for item in data:
        current_entries = to_int(first_value(item, [
            "current_entries",
            "entries",
            "tickets_sold",
            "sold",
            "sold_tickets"
        ], 0))

        max_entries = to_int(first_value(item, [
            "max_entries",
            "total_entries",
            "tickets_total",
            "total_tickets",
            "ticket_count"
        ], 0))

        ticket_price = to_float(first_value(item, [
            "ticket_price",
            "price",
            "entry_price"
        ], 0))

        sold_percent = round((current_entries / max_entries) * 100, 2) if max_entries else ""
        revenue_to_date = round(current_entries * ticket_price, 2)

        slug = first_value(item, ["slug"], "")
        raffle_id = first_value(item, ["id"], "")

        rows.append({
            "scraped_at": datetime.utcnow().isoformat(timespec="seconds"),
            "site": "WinnerStreak",
            "id": raffle_id,
            "slug": slug,
            "draw_name": first_value(item, ["title", "name", "raffle_title"]),
            "subtitle": first_value(item, ["subtitle", "description"]),
            "ticket_price": ticket_price,
            "currency": "GBP",
            "start_at": first_value(item, ["start_at", "start_date"]),
            "end_at": first_value(item, ["end_at", "end_date", "closing_date"]),
            "result_at": first_value(item, ["result_at", "draw_date"]),
            "prize_value": first_value(item, ["prize_value", "value"]),
            "cash_alternative": first_value(item, ["cash_alternative", "cash_alt"]),
            "current_entries": current_entries,
            "max_entries": max_entries,
            "sold_percent": sold_percent,
            "revenue_to_date": revenue_to_date,
            "is_open": first_value(item, ["is_open", "live", "status"]),
            "draw_method": first_value(item, ["draw_method"]),
            "category_ids": first_value(item, ["category", "categories"]),
            "thumbnail_url": first_value(item, ["image", "thumbnail", "thumbnail_url"]),
            "competition_url": f"https://www.thewinnerstreak.com/raffles/{slug}" if slug else ""
        })

    return pd.DataFrame(rows)


def clean_for_google_sheets(df):
    df = df.replace([float("inf"), float("-inf")], "")
    df = df.where(pd.notnull(df), "")
    df = df.astype(str)
    return df


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
        worksheet = sh.add_worksheet(title=TAB_NAME, rows=10000, cols=50)

    df = clean_for_google_sheets(df)
    values = df.values.tolist()

    existing_values = worksheet.get_all_values()

    if not existing_values:
        worksheet.update([df.columns.tolist()] + values)
    else:
        worksheet.append_rows(values, value_input_option="USER_ENTERED")


def main():
    data = fetch_winnerstreak()
    df = transform(data)

    if df.empty:
        raise Exception("No live raffles found from WinnerStreak API")

    save_to_google_sheet(df)

    print(f"Appended {len(df)} WinnerStreak raffles to Google Sheets")


if __name__ == "__main__":
    main()
