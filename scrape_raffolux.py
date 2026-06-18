import os
import json
import requests
import pandas as pd
import gspread

from datetime import datetime
from google.oauth2.service_account import Credentials


URL = "https://raffolux.com/api/raffle/active/site/all/instant-win"
SHEET_NAME = "Raffle Tracker"
TAB_NAME = "Raffolux"


def fetch_raffolux():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):
        return data

    return data.get("data", [])


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
        current_entries = to_int(item.get("soldTicketCount"))
        max_entries = to_int(item.get("totalTickets"))
        ticket_price = to_float(item.get("pricePerTicket"))

        sold_percent = round((current_entries / max_entries) * 100, 2) if max_entries else ""
        revenue_to_date = round(current_entries * ticket_price, 2)

        media = item.get("media") or {}
        config = item.get("configuration") or {}

        rows.append({
            "scraped_at": datetime.utcnow().isoformat(timespec="seconds"),
            "site": "Raffolux",
            "id": item.get("id"),
            "slug": item.get("slug"),
            "draw_name": item.get("title"),
            "subtitle": item.get("summary"),
            "ticket_price": ticket_price,
            "currency": "GBP",
            "start_at": "",
            "end_at": item.get("drawDate"),
            "result_at": item.get("drawDate"),
            "prize_value": item.get("prizeValue"),
            "cash_alternative": item.get("prizeCashAlternativeValue"),
            "current_entries": current_entries,
            "max_entries": max_entries,
            "sold_percent": sold_percent,
            "revenue_to_date": revenue_to_date,
            "is_cash": "",
            "is_open": True,
            "draw_method": item.get("drawType"),
            "instant_win_count": len(config.get("instants", [])),
            "prize_count": "",
            "default_tickets": config.get("startingTicketCount"),
            "ticket_limit_per_user": item.get("maximumAllowedTickets"),
            "category_ids": item.get("category"),
            "featured": config.get("featured"),
            "jackpot": config.get("jackpot"),
            "thumbnail_url": media.get("thumbnail"),
            "competition_url": f"https://raffolux.com/raffle/{item.get('slug')}"
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

    try:
        worksheet = sh.worksheet(TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(
            title=TAB_NAME,
            rows=500,
            cols=len(df.columns)
        )

    df = clean_for_google_sheets(df)
    values = df.values.tolist()

    existing_values = worksheet.get_all_values()

    if not existing_values:
        worksheet.update([df.columns.tolist()] + values)
    else:
        worksheet.append_rows(values, value_input_option="USER_ENTERED")

    worksheet.resize(
        rows=len(worksheet.get_all_values()) + 100,
        cols=len(df.columns)
    )

    print(f"Updated sheet: {SHEET_NAME}")
    print(f"Updated tab: {TAB_NAME}")
    print(f"Rows written/appended: {len(values)}")


def main():
    data = fetch_raffolux()
    df = transform(data)

    if df.empty:
        raise Exception("No Raffolux raffles found")

    save_to_google_sheet(df)

    print(f"Appended {len(df)} Raffolux raffles to Google Sheets")


if __name__ == "__main__":
    main()
