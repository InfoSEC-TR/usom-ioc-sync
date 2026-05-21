import os
import requests
import pandas as pd
from datetime import datetime

BASE_URL = "https://www.usom.gov.tr/api/address/index"

OUTPUT_DIR = "output"

IOC_TYPES = {
    "ip": "usom_ip.xlsx",
    "domain": "usom_domain.xlsx",
    "url": "usom_url.xlsx"
}


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_existing_iocs(excel_path):
    if not os.path.exists(excel_path):
        return set()

    try:
        df = pd.read_excel(excel_path)

        if "IOC" not in df.columns:
            return set()

        return set(df["IOC"].astype(str).tolist())

    except Exception:
        return set()


def append_to_excel(excel_path, new_rows):
    if os.path.exists(excel_path):
        existing_df = pd.read_excel(excel_path)
        new_df = pd.DataFrame(new_rows)

        final_df = pd.concat([existing_df, new_df], ignore_index=True)

    else:
        final_df = pd.DataFrame(new_rows)

    final_df.to_excel(excel_path, index=False)


def fetch_iocs(ioc_type):
    page = 1
    collected = []

    while True:
        params = {
            "type": ioc_type,
            "page": page
        }

        response = requests.get(BASE_URL, params=params, timeout=60)

        if response.status_code != 200:
            break

        try:
            data = response.json()
        except Exception:
            break

        models = data.get("models", [])

        if not models:
            break

        collected.extend(models)

        print(f"[+] {ioc_type} | Page {page}")

        page += 1

    return collected


def process_type(ioc_type, filename):
    excel_path = os.path.join(OUTPUT_DIR, filename)

    existing_iocs = load_existing_iocs(excel_path)

    fetched = fetch_iocs(ioc_type)

    new_rows = []

    for item in fetched:
        ioc = item.get("url")

        if not ioc:
            continue

        if ioc in existing_iocs:
            continue

        new_rows.append({
            "IOC": ioc,
            "Type": item.get("type"),
            "Source": item.get("source"),
            "Description": item.get("desc"),
            "Criticality": item.get("criticality_level"),
            "ConnectionType": item.get("connectiontype"),
            "Date": item.get("date"),
            "AddedAt": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })

    if new_rows:
        append_to_excel(excel_path, new_rows)
        print(f"[+] Yeni IOC: {len(new_rows)}")


def main():
    ensure_output_dir()

    for ioc_type, filename in IOC_TYPES.items():
        process_type(ioc_type, filename)


if __name__ == "__main__":
    main()
