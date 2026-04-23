"""
CFO Report Generator
Exports executive-ready Excel reports with formatted sheets,
summary stats, and chart-ready data.
"""

import pandas as pd
import io
from datetime import datetime


def generate_executive_summary(df: pd.DataFrame, spend_col: str = "spend",
                                category_col: str = "category",
                                supplier_col: str = "supplier") -> dict:
    """Generate key metrics for CFO overview."""
    summary = {}

    if spend_col in df.columns:
        summary["total_spend"] = df[spend_col].sum()
        summary["avg_spend"] = df[spend_col].mean()
        summary["median_spend"] = df[spend_col].median()
        summary["max_single_spend"] = df[spend_col].max()

    if category_col in df.columns:
        summary["num_categories"] = df[category_col].nunique()
        top_cats = df.groupby(category_col)[spend_col].sum().nlargest(5)
        summary["top_5_categories"] = top_cats.to_dict()
        summary["top_5_pct"] = (top_cats.sum() / df[spend_col].sum() * 100).round(1)

    if supplier_col in df.columns:
        summary["num_suppliers"] = df[supplier_col].nunique()
        top_suppliers = df.groupby(supplier_col)[spend_col].sum().nlargest(10)
        summary["top_10_suppliers"] = top_suppliers.to_dict()
        summary["top_10_pct"] = (top_suppliers.sum() / df[spend_col].sum() * 100).round(1)

    return summary


def generate_spend_by_category(df: pd.DataFrame, spend_col: str = "spend",
                                category_col: str = "category") -> pd.DataFrame:
    """Category breakdown with share percentages."""
    if category_col not in df.columns or spend_col not in df.columns:
        return pd.DataFrame()

    cat_spend = df.groupby(category_col)[spend_col].agg(["sum", "mean", "count"])
    cat_spend.columns = ["Total Spend", "Avg per Transaction", "Transaction Count"]
    cat_spend["Share %"] = (cat_spend["Total Spend"] / cat_spend["Total Spend"].sum() * 100).round(1)
    cat_spend = cat_spend.sort_values("Total Spend", ascending=False)
    return cat_spend.reset_index()


def generate_supplier_concentration(df: pd.DataFrame, spend_col: str = "spend",
                                     supplier_col: str = "supplier",
                                     category_col: str = "category") -> pd.DataFrame:
    """Supplier concentration analysis per category."""
    if not all(c in df.columns for c in [spend_col, supplier_col, category_col]):
        return pd.DataFrame()

    rows = []
    for cat in df[category_col].unique():
        cat_df = df[df[category_col] == cat]
        total = cat_df[spend_col].sum()
        top_supplier = cat_df.groupby(supplier_col)[spend_col].sum().nlargest(1)

        if len(top_supplier) > 0 and total > 0:
            rows.append({
                "Category": cat,
                "Total Spend": total,
                "Top Supplier": top_supplier.index[0],
                "Top Supplier Spend": top_supplier.values[0],
                "Concentration %": round(top_supplier.values[0] / total * 100, 1),
                "Supplier Count": cat_df[supplier_col].nunique(),
            })

    result = pd.DataFrame(rows).sort_values("Concentration %", ascending=False)
    return result


def export_cfo_excel(df: pd.DataFrame, spend_col: str = "spend",
                     category_col: str = "category",
                     supplier_col: str = "supplier") -> bytes:
    """Generate a multi-sheet Excel report for CFO."""

    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

        # Sheet 1: Executive Summary
        summary = generate_executive_summary(df, spend_col, category_col, supplier_col)
        summary_df = pd.DataFrame([
            {"Metric": "Total Spend", "Value": f"€{summary.get('total_spend', 0):,.0f}"},
            {"Metric": "Number of Categories", "Value": str(summary.get("num_categories", 0))},
            {"Metric": "Number of Suppliers", "Value": str(summary.get("num_suppliers", 0))},
            {"Metric": "Top 5 Categories % of Spend", "Value": f"{summary.get('top_5_pct', 0)}%"},
            {"Metric": "Top 10 Suppliers % of Spend", "Value": f"{summary.get('top_10_pct', 0)}%"},
            {"Metric": "Largest Single Spend", "Value": f"€{summary.get('max_single_spend', 0):,.0f}"},
            {"Metric": "Report Generated", "Value": datetime.now().strftime("%Y-%m-%d %H:%M")},
        ])
        summary_df.to_excel(writer, sheet_name="Executive Summary", index=False)

        # Sheet 2: Spend by Category
        cat_df = generate_spend_by_category(df, spend_col, category_col)
        if len(cat_df) > 0:
            cat_df.to_excel(writer, sheet_name="Category Breakdown", index=False)

        # Sheet 3: Supplier Concentration
        conc_df = generate_supplier_concentration(df, spend_col, supplier_col, category_col)
        if len(conc_df) > 0:
            conc_df.to_excel(writer, sheet_name="Supplier Concentration", index=False)

        # Sheet 4: Raw Data
        df.to_excel(writer, sheet_name="Raw Data", index=False)

    return buffer.getvalue()


if __name__ == "__main__":
    # Test with sample data
    test_df = pd.DataFrame({
        "category": ["IT", "IT", "Marketing", "Marketing", "Cloud"] * 10,
        "supplier": ["SAP", "Microsoft", "HubSpot", "WPP", "AWS"] * 10,
        "spend": [50000, 30000, 20000, 15000, 80000] * 10,
    })

    summary = generate_executive_summary(test_df)
    print("Executive Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
