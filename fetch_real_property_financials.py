from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import requests


DATASET_ID = "myei-c3fa"
DATASET_NAME = "DOF: Cooperative Comparable Rental Income (Citywide)"
DATASET_PORTAL = "https://data.cityofnewyork.us"
SOCRATA_API = f"{DATASET_PORTAL}/resource/{DATASET_ID}.json"

# NYC borough code comes from the first digit of boro_block_lot.
BOROUGH_MAP = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}

# Columns we intentionally use. Keeping this explicit helps with explainability.
SELECT_COLUMNS = [
    "boro_block_lot",
    "address",
    "neighborhood",
    "building_classification",
    "gross_sqft",
    "estimated_gross_income",
    "estimated_expense",
    "net_operating_income",
    "report_year",
]


def _clean_text(value: Any) -> str:
    """Normalize whitespace and safely handle null-ish values."""
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _map_property_type(building_classification: str) -> str:
    """
    Simplified mapping from NYC building classification code to a demo-friendly property type.

    This is intentionally coarse. The goal is not to recreate NYC's full property taxonomy,
    but to produce a small, readable property_type field for the app UI and SQL schema.
    """
    cls = _clean_text(building_classification).upper()

    if cls.startswith("D") or "CO-OP" in cls or "CONDOMINIUM" in cls:
        return "multifamily"
    if cls.startswith("O"):
        return "office"
    if cls.startswith("K"):
        return "retail"
    if cls.startswith("E") or cls.startswith("F"):
        return "industrial"
    return "mixed-use"


def _build_query_params(report_year: int, limit: int) -> dict[str, str]:
    """
    Build Socrata query parameters once so they can be used both for the request
    and for exact provenance in metadata.
    """
    where = (
        f"report_year='{report_year}' "
        "and address is not null "
        "and gross_sqft is not null "
        "and estimated_gross_income is not null "
        "and estimated_expense is not null "
        "and net_operating_income is not null"
    )

    return {
        "$select": ",".join(SELECT_COLUMNS),
        "$where": where,
        "$order": "estimated_gross_income DESC",
        "$limit": str(limit),
    }


def _build_exact_request_url(params: dict[str, str]) -> str:
    """Store the exact request URL for reproducibility and handoff documentation."""
    return f"{SOCRATA_API}?{urlencode(params)}"


def fetch_raw_rows(report_year: int, limit: int, timeout_s: int = 45) -> tuple[list[dict], str]:
    """
    Fetch raw rows from NYC Open Data.

    Returns:
      - raw JSON rows
      - exact request URL used
    """
    params = _build_query_params(report_year=report_year, limit=limit)
    exact_request_url = _build_exact_request_url(params)

    response = requests.get(SOCRATA_API, params=params, timeout=timeout_s)
    response.raise_for_status()

    return response.json(), exact_request_url


def _stable_property_id_from_bbl(bbl: str) -> int:
    """
    Convert boro_block_lot into a deterministic integer property_id.

    Why:
      - Stable across runs
      - Easy to explain
      - Better than assigning 1..N, which changes if ordering changes
    """
    cleaned = "".join(ch for ch in str(bbl) if ch.isdigit())
    if not cleaned:
        raise ValueError(f"Invalid boro_block_lot for property_id: {bbl}")
    return int(cleaned)


def transform_rows(rows: list[dict], n_records: int) -> pd.DataFrame:
    """
    Clean raw Socrata rows into the final property/financial dataset.

    Output columns are designed to support:
      - SQL seeding
      - app display
      - possible downstream regression experiments
    """
    frame = pd.DataFrame(rows)

    if frame.empty:
        raise RuntimeError("No rows were returned from the Socrata API query.")

    numeric_cols = [
        "gross_sqft",
        "estimated_gross_income",
        "estimated_expense",
        "net_operating_income",
    ]
    for col in numeric_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame = frame.dropna(
        subset=[
            "boro_block_lot",
            "address",
            "gross_sqft",
            "estimated_gross_income",
            "estimated_expense",
            "net_operating_income",
        ]
    ).copy()

    frame["address"] = frame["address"].map(_clean_text)
    frame["neighborhood"] = frame["neighborhood"].fillna("").map(_clean_text)
    frame["building_classification"] = frame["building_classification"].fillna("").map(_clean_text)

    # Keep one row per BBL. Since we already sort by estimated_gross_income DESC in the query,
    # keeping the first row preserves the highest-income record if duplicates exist.
    frame = frame.drop_duplicates(subset=["boro_block_lot"], keep="first")

    borough = frame["boro_block_lot"].astype(str).str[0].map(BOROUGH_MAP).fillna("New York")
    neighborhood = frame["neighborhood"].replace("", pd.NA)

    # More informative than borough alone, but still compact.
    frame["metro_area"] = neighborhood.combine_first(borough) + " / " + borough

    frame["property_type"] = frame["building_classification"].map(_map_property_type)
    frame["property_id"] = frame["boro_block_lot"].map(_stable_property_id_from_bbl)

    final = frame.head(n_records).copy()

    final = final[
        [
            "property_id",
            "boro_block_lot",
            "address",
            "metro_area",
            "neighborhood",
            "building_classification",
            "property_type",
            "gross_sqft",
            "estimated_gross_income",
            "net_operating_income",
            "estimated_expense",
            "report_year",
        ]
    ].rename(
        columns={
            "gross_sqft": "sq_footage",
            "estimated_gross_income": "revenue",
            "net_operating_income": "net_income",
            "estimated_expense": "expenses",
        }
    )

    # Use integer-like types where reasonable for cleaner CSV/SQL output.
    final["sq_footage"] = final["sq_footage"].astype(int)
    final["revenue"] = final["revenue"].astype(float)
    final["net_income"] = final["net_income"].astype(float)
    final["expenses"] = final["expenses"].astype(float)

    return final


def _sql_quote(value: str) -> str:
    """Escape single quotes for seed SQL generation."""
    return str(value).replace("'", "''")


def build_seed_sql(final: pd.DataFrame) -> str:
    """
    Generate a simple seed.sql file for the assignment's required tables.

    This is not meant to be a general SQL builder—just a reproducible handoff artifact.
    """
    prop_values = []
    fin_values = []

    for _, row in final.iterrows():
        prop_values.append(
            "("
            f"{int(row['property_id'])}, "
            f"'{_sql_quote(row['address'])}', "
            f"'{_sql_quote(row['metro_area'])}', "
            f"{int(row['sq_footage'])}, "
            f"'{_sql_quote(row['property_type'])}'"
            ")"
        )
        fin_values.append(
            "("
            f"{int(row['property_id'])}, "
            f"{float(row['revenue']):.2f}, "
            f"{float(row['net_income']):.2f}, "
            f"{float(row['expenses']):.2f}"
            ")"
        )

    return "\n".join(
        [
            "INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES",
            ",\n".join(prop_values),
            "ON CONFLICT(property_id) DO UPDATE SET",
            "    address = EXCLUDED.address,",
            "    metro_area = EXCLUDED.metro_area,",
            "    sq_footage = EXCLUDED.sq_footage,",
            "    property_type = EXCLUDED.property_type;",
            "",
            "INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES",
            ",\n".join(fin_values),
            "ON CONFLICT(property_id) DO UPDATE SET",
            "    revenue = EXCLUDED.revenue,",
            "    net_income = EXCLUDED.net_income,",
            "    expenses = EXCLUDED.expenses;",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch NYC property financials and build demo artifacts.")
    parser.add_argument("--report-year", type=int, default=2022)
    parser.add_argument("--records", type=int, default=20)
    parser.add_argument("--fetch-limit", type=int, default=5000)
    parser.add_argument("--csv-output", type=Path, default=Path("data/real_property_financials_nyc.csv"))
    parser.add_argument("--metadata-output", type=Path, default=Path("data/real_property_financials_nyc_metadata.json"))
    parser.add_argument("--seed-output", type=Path, default=Path("sql/seed.sql"))
    args = parser.parse_args()

    raw_rows, exact_request_url = fetch_raw_rows(args.report_year, args.fetch_limit)
    final = transform_rows(raw_rows, args.records)

    if len(final) < args.records:
        raise RuntimeError(
            f"Requested {args.records} records, but only {len(final)} were available after filtering."
        )

    args.csv_output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.seed_output.parent.mkdir(parents=True, exist_ok=True)

    final.to_csv(args.csv_output, index=False)
    args.seed_output.write_text(build_seed_sql(final), encoding="utf-8")

    metadata = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dataset_name": DATASET_NAME,
        "dataset_id": DATASET_ID,
        "dataset_portal": DATASET_PORTAL,
        "api_endpoint": SOCRATA_API,
        "exact_request_url": exact_request_url,
        "query": {
            "report_year": args.report_year,
            "records_requested_for_output": args.records,
            "fetch_limit": args.fetch_limit,
        },
        "output_files": {
            "csv": str(args.csv_output),
            "metadata_json": str(args.metadata_output),
            "seed_sql": str(args.seed_output),
        },
        "columns_used": SELECT_COLUMNS,
        "notes": [
            "Property records are sourced from NYC DOF Cooperative Comparable Rental Income data.",
            "property_type is a simplified mapping derived from building_classification.",
            "net_income in the demo dataset is populated from net_operating_income, not GAAP net income.",
        ],
    }

    args.metadata_output.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote {len(final)} records to {args.csv_output}")
    print(f"Wrote metadata to {args.metadata_output}")
    print(f"Regenerated SQL seed file at {args.seed_output}")
    print(f"Exact request URL: {exact_request_url}")


if __name__ == "__main__":
    main()

