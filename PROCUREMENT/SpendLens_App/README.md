# 🔴 SpendLens — AI-Powered Procurement Intelligence

A Panel-based dashboard that turns messy procurement data into CFO-ready insights.
Built to adapt to any spend dataset using AI-powered column mapping and data cleanup.

## Quick Start

### 1. Install dependencies

```bash
cd procurement-tool
pip install -r requirements.txt
```

### 2. Run the dashboard

```bash
panel serve app.py --show --autoreload
```

This opens the dashboard in your browser at `http://localhost:5006`

### 3. For development (auto-reload on save)

```bash
python app.py
```

## Project Structure

```
procurement-tool/
├── app.py                  # Main Panel dashboard
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── data/
│   └── sample_spend.csv   # Sample dataset for testing
└── modules/
    ├── __init__.py
    ├── column_mapper.py    # AI-powered column name mapping
    ├── data_cleanup.py     # Data cleaning pipeline
    └── cfo_reports.py      # Excel report generator
```

## Features

### ✅ Working Now
- **Default Parloa dataset** — your existing analysis loads automatically
- **Interactive charts** — spend evolution, category breakdown, CAGR, risk bubble map, treemap
- **KPI cards** — total spend, critical risks, single-source count, avg concentration
- **File upload** — drag in CSV/Excel files
- **Rule-based column mapping** — recognizes Vendor/Supplier/Lieferant/Provider etc.
- **Data cleanup** — removes junk rows, fixes German number formats, standardizes vendors
- **CFO Excel export** — multi-sheet report with executive summary
- **Data explorer table** — sortable, filterable view of your data

### 🔜 Next Steps (build in this order)
1. **AI column mapping** — add your Claude API key to auto-map unknown columns
2. **Vendor deduplication** — expand the alias dictionary for your specific suppliers
3. **Budget vs Actual** — add a budget_k column and compute variance
4. **Trend forecasting** — rolling averages and simple predictions
5. **Chat interface** — ask questions about your data in natural language
6. **Deploy** — host on Hugging Face Spaces or a cloud VM

## AI Column Mapping

The tool recognizes these column name patterns automatically:

| Standard Field | Recognized Names |
|---|---|
| supplier | vendor, provider, lieferant, kreditor, company |
| spend | amount, total, cost, betrag, invoice_total, rechnungsbetrag |
| category | spend_category, warengruppe, commodity, cost_center |
| date | invoice_date, datum, posting_date, buchungsdatum |
| region | country, location, land, geography |

For columns it can't match, it sends them to Claude API for intelligent mapping.

## Environment Variables (optional)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # enables AI column mapping
```

## Data Formats Supported

- CSV (UTF-8, Latin-1)
- Excel (.xlsx, .xls)
- German number format (1.234,56)
- German date format (22.04.2026)
- Currency symbols (€, $, £)
- Accounting negatives: (1234)
