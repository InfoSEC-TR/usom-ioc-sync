import os
import time
import json
import requests
import pandas as pd
from datetime import datetime, timezone

API_URL = "https://siberguvenlik.gov.tr/api/address/index"

OUTPUT_DIR = "output"
STATE_FILE = os.path.join(OUTPUT_DIR, "state.json")
STATS_FILE = os.path.join(OUTPUT_DIR, "stats.json")

IOC_TYPES = {
    "ip": "usom_ip",
    "domain": "usom_domain",
    "url": "usom_url"
}

PER_PAGE = 1000
INITIAL_BOOTSTRAP_PAGES = 5
MAX_RETRIES = 5
TIMEOUT = 30
STOP_AFTER_KNOWN = 40

HEADERS = {
    "User-Agent": "usom-ioc-sync/1.0",
    "Accept": "application/json"
}


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_state():
    if not os.path.exists(STATE_FILE):
        return {ioc_type: 0 for ioc_type in IOC_TYPES}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        for ioc_type in IOC_TYPES:
            state.setdefault(ioc_type, 0)

        return state
    except Exception:
        return {ioc_type: 0 for ioc_type in IOC_TYPES}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def output_path(base_name, extension):
    return os.path.join(OUTPUT_DIR, f"{base_name}.{extension}")


def load_existing_iocs(csv_path):
    if not os.path.exists(csv_path):
        return set()

    try:
        df = pd.read_csv(csv_path)

        if "IOC" not in df.columns:
            return set()

        return set(df["IOC"].astype(str).str.strip().str.lower().tolist())
    except Exception as e:
        print(f"[-] CSV okunamadı: {csv_path} | {e}")
        return set()


def normalize_ioc(value):
    if not value:
        return ""

    return str(value).strip().lower()


def fetch_page(session, ioc_type, page):
    delay = 10

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                API_URL,
                params={
                    "type": ioc_type,
                    "page": page,
                    "per-page": PER_PAGE
                },
                headers=HEADERS,
                timeout=TIMEOUT
            )

            if response.status_code == 429:
                print(f"[!] 429 Rate Limit | {ioc_type} page={page} | {delay}s bekleniyor")
                time.sleep(delay)
                delay *= 2
                continue

            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"[!] Hata | {ioc_type} page={page} attempt={attempt} | {e}")
            time.sleep(delay)
            delay *= 2

    raise RuntimeError(f"{ioc_type} page={page} alınamadı")


def fetch_delta_iocs(ioc_type, max_known_id):
    session = requests.Session()

    page = 1
    collected = []
    new_max_id = max_known_id
    consecutive_known = 0
    total_count = 0
    page_count = 1

    while True:
        data = fetch_page(session, ioc_type, page)

        page_count = data.get("pageCount", 1)
        total_count = data.get("totalCount", 0)
        models = data.get("models", [])

        if max_known_id == 0:
            page_limit = min(page_count, INITIAL_BOOTSTRAP_PAGES)
        else:
            page_limit = page_count

        print(
            f"[+] {ioc_type} | page={page}/{page_count} | "
            f"records={len(models)} | max_known_id={max_known_id} | "
            f"page_limit={page_limit}"
        )

        if not models:
            break

        for item in models:
            try:
                item_id = int(item.get("id"))
            except Exception:
                continue

            if item_id > new_max_id:
                new_max_id = item_id

            if max_known_id == 0:
                collected.append(item)
                continue

            if item_id <= max_known_id:
                consecutive_known += 1
            else:
                consecutive_known = 0
                collected.append(item)

        if max_known_id != 0 and consecutive_known >= STOP_AFTER_KNOWN:
            print(f"[+] {ioc_type} | bilinen kayıtlara ulaşıldı, duruluyor")
            break

        if page >= page_limit:
            break

        page += 1
        time.sleep(1)

    return collected, new_max_id, total_count, page_count


def record_to_row(item):
    return {
        "IOC": normalize_ioc(item.get("url")),
        "Type": item.get("type"),
        "Source": item.get("source"),
        "Description": item.get("desc"),
        "Criticality": item.get("criticality_level"),
        "ConnectionType": item.get("connectiontype"),
        "USOM_ID": item.get("id"),
        "Date": item.get("date"),
        "AddedAt_UTC": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    }


def save_outputs(base_name, rows):
    csv_path = output_path(base_name, "csv")
    txt_path = output_path(base_name, "txt")

    new_df = pd.DataFrame(rows)

    if os.path.exists(csv_path):
        old_df = pd.read_csv(csv_path)
        final_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df.drop_duplicates(subset=["IOC"], inplace=True)
    final_df.sort_values(by=["USOM_ID"], ascending=False, inplace=True, na_position="last")

    final_df.to_csv(csv_path, index=False, encoding="utf-8")

    iocs = final_df["IOC"].dropna().astype(str).str.strip()
    iocs = sorted(set(ioc for ioc in iocs if ioc))

    if base_name == "usom_ip":
        iocs = [
            ioc if "/" in ioc else f"{ioc}/32"
            for ioc in iocs
        ]

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(iocs) + ("\n" if iocs else ""))


def process_type(ioc_type, base_name, state):
    csv_path = output_path(base_name, "csv")

    max_known_id = int(state.get(ioc_type, 0))
    existing_iocs = load_existing_iocs(csv_path)

    records, new_max_id, total_count, page_count = fetch_delta_iocs(ioc_type, max_known_id)

    new_rows = []

    for item in records:
        row = record_to_row(item)
        ioc = row["IOC"]

        if not ioc:
            continue

        if ioc in existing_iocs:
            continue

        new_rows.append(row)

    if new_rows:
        save_outputs(base_name, new_rows)

    state[ioc_type] = max(new_max_id, max_known_id)

    return {
        "type": ioc_type,
        "base_name": base_name,
        "previous_max_id": max_known_id,
        "new_max_id": state[ioc_type],
        "fetched_records": len(records),
        "new_records": len(new_rows),
        "api_total_count": total_count,
        "api_page_count": page_count,
        "initial_bootstrap_pages": INITIAL_BOOTSTRAP_PAGES
    }


def write_stats(results, state):
    stats = {
        "last_update_utc": datetime.now(timezone.utc).isoformat(),
        "per_page": PER_PAGE,
        "initial_bootstrap_pages": INITIAL_BOOTSTRAP_PAGES,
        "stop_after_known": STOP_AFTER_KNOWN,
        "state": state,
        "results": results
    }

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def main():
    ensure_output_dir()

    state = load_state()
    results = []

    for ioc_type, base_name in IOC_TYPES.items():
        print(f"\n[+] İşleniyor: {ioc_type}")

        try:
            result = process_type(ioc_type, base_name, state)
            results.append(result)

            print(
                f"[+] {ioc_type} tamamlandı | "
                f"yeni={result['new_records']} | "
                f"max_id={result['new_max_id']}"
            )

        except Exception as e:
            print(f"[-] {ioc_type} hata: {e}")
            results.append({
                "type": ioc_type,
                "error": str(e)
            })

    save_state(state)
    write_stats(results, state)


if __name__ == "__main__":
    main()
