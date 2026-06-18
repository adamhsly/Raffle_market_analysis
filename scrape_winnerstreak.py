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

    while True:
        params = {
            "status": "live",
            "perPage": 25,
            "orderBy": "end_date",
            "page": page
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }

        response = requests.get(URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        payload = response.json()
        items = payload.get("data", [])

        if not items:
            break

        all_items.extend(items)

        meta = payload.get("meta", {})
        last_page = meta.get("last_page", page)

        if page >= last_page:
            break

        page += 1

    return all_items


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


def category_names(categories):
    if not categories:
        return ""
    return ", ".join([c.get("name", "") for c in categories if c.get("name")])


def transform(data):
    rows = []

    for item in data:
        current_entries = to_int(item.get("ticketsSold"))
        max_entries = to_int(item.get("numberOfTickets"))

        # WinnerStreak price is in pence
        ticket_price = round(to_float(item.get("price")) / 100, 2)

        sold_percent = round((current_entries / max_entries) * 100, 2) if max_entries else ""
        revenue_to_date = round(current_entries * ticket_price, 2)

        image = item.get("image") or {}

        rows.append({
            "scraped_at": datetime.utcnow().isoformat(timespec="seconds"),
            "site": "WinnerStreak",
            "id": item.get("id"),
            "slug": item.get("slug"),
            "draw_name": item.get("title"),
            "subtitle": item.get("description"),
            "ticket_price": ticket_price,
            "currency": "GBP",
            "start_at": item.get("startDate"),
            "end_at": item.get("endDate"),
            "result_at": item.get("drawDate"),
            "prize_value": item.get("prizeValue"),
            "cash_alternative": item.get("cashAlternative"),
            "current_entries": current_entries,
            "max_entries": max_entries,
            "sold_percent": sold_percent,
            "revenue_to_date": revenue_to_date,
            "is_cash": "",
            "is_open": item.get("status") == "live",
            "status": item.get("status"),
            "draw_method": "auto" if item.get("autoDraw") else "manual",
            "instant_win_count": item.get("instantWinsCount"),
            "prize_count": len(item.get("prizes", [])),
            "default_tickets": item.get("defaultTicketQuantity"),
            "ticket_limit_per_user": item.get("maxTicketsPerUser"),
            "category_ids": category_names(item.get("categories", [])),
            "thumbnail_url": image.get("url"),
            "competition_url": f"https://www.thewinnerstreak.com/raffles/{item.get('slug')}"
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
    data = fetch_winnerstreak()
    df = transform(data)

    if df.empty:
        raise Exception("No WinnerStreak raffles found")

    save_to_google_sheet(df)

    print(f"Appended {len(df)} WinnerStreak raffles to Google Sheets")


if __name__ == "__main__":
    main()
