# usom-ioc-sync

Automatic USOM IOC collector and updater.

This project automatically pulls IOC feeds from USOM and keeps them updated inside the repository using GitHub Actions.

## Features

- Automatic hourly IOC sync
- Incremental update logic
- Duplicate IOC filtering
- CSV export support
- TXT export support
- GitHub Actions automation
- Supports:
  - IP
  - Domain
  - URL

## Output Files

Generated files are stored under:

```plaintext
output/
```

Example:

```plaintext
output/usom_ip.csv
output/usom_domain.csv
output/usom_url.csv

output/usom_ip.txt
output/usom_domain.txt
output/usom_url.txt

output/state.json
output/stats.json
```

## CSV Columns

| Column | Description |
|---|---|
| IOC | IOC value |
| Type | IOC type |
| Source | IOC source |
| Description | IOC description |
| Criticality | Criticality level |
| ConnectionType | Connection type |
| USOM_ID | USOM record ID |
| Date | Original USOM date |
| AddedAt_UTC | Sync timestamp |

## GitHub Actions

Workflow automatically runs every hour.

Workflow file:

```plaintext
.github/workflows/usom-ioc-sync.yml
```

Manual execution is also supported from:

```plaintext
Actions -> USOM IOC Sync -> Run workflow
```

## Installation

Clone repository:

```bash
git clone https://github.com/USERNAME/usom-ioc-sync.git
cd usom-ioc-sync
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run manually:

```bash
python usom_ioc_sync.py
```

## Requirements

- Python 3.11+
- pandas
- requests

## Incremental Sync Logic

The project stores the latest processed USOM IDs inside:

```plaintext
output/state.json
```

On next executions:
- Only new records are fetched
- Existing IOCs are skipped
- Duplicate entries are prevented

## Statistics

Sync statistics are written to:

```plaintext
output/stats.json
```

Includes:
- Last update time
- API statistics
- New IOC counts
- Sync metadata

## License

MIT License
