from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


# Keep the property type vocabulary small and explicit.
# This is easier to defend in an interview than trying to infer everything dynamically.
PROPERTY_TYPES = ["industrial", "office", "retail", "multifamily", "mixed-use"]


@dataclass(frozen=True)
class PropertyQueryFilters:
    """
    Simple parsed filters derived from a user question.

    We keep this intentionally small:
      - metro_area: best matched metro/neighborhood string from the DB
      - property_type: one of the normalized property types
      - min_revenue: optional lower bound if user mentions revenue threshold
      - limit: optional requested row count, defaults handled in query layer
    """
    metro_area: Optional[str] = None
    property_type: Optional[str] = None
    min_revenue: Optional[float] = None
    limit: Optional[int] = None


class PropertyService:
    """
    Service layer for querying the properties + financials tables.

    Design goals:
      - minimal and explainable
      - robust enough for simple natural-language filtering
      - no brittle over-engineered NLP
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    def list_metro_areas(self) -> list[str]:
        """Return all metro areas currently available in the properties table."""
        query = text("SELECT DISTINCT metro_area FROM properties ORDER BY metro_area")
        frame = pd.read_sql_query(query, self.engine)
        return frame["metro_area"].dropna().astype(str).tolist()

    def parse_filters_from_question(self, question: str) -> PropertyQueryFilters:
        """
        Parse a few simple, explainable filters from a user question.

        This is intentionally not a full NLP system.
        We only extract:
          - metro area (best match against known metro areas)
          - property type
          - revenue threshold phrases like "over 1000000" or "above 500000"
          - row count phrases like "top 10"
        """
        lowered = question.lower()
        metro_match = None
        property_type_match = None
        min_revenue = None
        limit = None

        metros = self.list_metro_areas()

        # 1) Exact substring match against known metro areas.
        for metro in metros:
            if metro.lower() in lowered:
                metro_match = metro
                break

        # 2) Looser fallback: handle phrases like "Queens region" or "Bronx metro".
        if not metro_match:
            region_pattern = re.compile(r"\b([a-z][a-z\s\-]+?)\s+(region|metro|area)\b", re.IGNORECASE)
            match = region_pattern.search(question)
            if match:
                candidate = match.group(1).strip().lower()
                for metro in metros:
                    if candidate in metro.lower():
                        metro_match = metro
                        break

        # 3) Property type lookup from a fixed vocabulary.
        for property_type in PROPERTY_TYPES:
            if property_type in lowered:
                property_type_match = property_type
                break

        # 4) Very simple revenue threshold extraction.
        # Supports phrases like:
        #   "revenue over 1000000"
        #   "revenue above 500000"
        #   "with revenue greater than 2000000"
        revenue_pattern = re.compile(
            r"revenue\s+(?:over|above|greater than|>=?)\s+\$?([\d,]+(?:\.\d+)?)",
            re.IGNORECASE,
        )
        revenue_match = revenue_pattern.search(question)
        if revenue_match:
            raw_value = revenue_match.group(1).replace(",", "")
            try:
                min_revenue = float(raw_value)
            except ValueError:
                min_revenue = None

        # 5) Optional top-N extraction for demo-friendly questions like "top 10".
        top_n_pattern = re.compile(r"\btop\s+(\d{1,3})\b", re.IGNORECASE)
        top_match = top_n_pattern.search(question)
        if top_match:
            try:
                limit = int(top_match.group(1))
            except ValueError:
                limit = None

        return PropertyQueryFilters(
            metro_area=metro_match,
            property_type=property_type_match,
            min_revenue=min_revenue,
            limit=limit,
        )

    def query_properties(
        self,
        metro_area: str | None = None,
        property_type: str | None = None,
        min_revenue: float | None = None,
        limit: int = 25,
    ) -> pd.DataFrame:
        """
        Query joined property + financial data with optional filters.

        Notes:
          - metro_area uses case-insensitive partial matching to be less brittle.
          - property_type is normalized to lowercase.
          - revenue sorting is descending because financial ranking is useful in demos.
        """
        clauses = []
        params: dict[str, Any] = {"limit": limit}

        if metro_area:
            clauses.append("LOWER(p.metro_area) LIKE :metro_area")
            params["metro_area"] = f"%{metro_area.lower()}%"

        if property_type:
            clauses.append("LOWER(p.property_type) = :property_type")
            params["property_type"] = property_type.lower()

        if min_revenue is not None:
            clauses.append("f.revenue >= :min_revenue")
            params["min_revenue"] = float(min_revenue)

        where_sql = ""
        if clauses:
            where_sql = "WHERE " + " AND ".join(clauses)

        query = text(
            f"""
            SELECT
                p.property_id,
                p.address,
                p.metro_area,
                p.sq_footage,
                p.property_type,
                f.revenue,
                f.net_income,
                f.expenses
            FROM properties p
            JOIN financials f
              ON p.property_id = f.property_id
            {where_sql}
            ORDER BY f.revenue DESC, p.property_id ASC
            LIMIT :limit
            """
        )

        return pd.read_sql_query(query, self.engine, params=params)

    def aggregate_financials(
        self,
        metro_area: str | None = None,
        property_type: str | None = None,
    ) -> dict[str, float]:
        """
        Return aggregate financial totals for the current selection.

        This is useful for:
          - dashboard KPI cards
          - chat responses like "total revenue in Queens"
        """
        query = """
            SELECT
                COALESCE(SUM(f.revenue), 0) AS total_revenue,
                COALESCE(SUM(f.net_income), 0) AS total_net_income,
                COALESCE(SUM(f.expenses), 0) AS total_expenses
            FROM financials f
            JOIN properties p
              ON p.property_id = f.property_id
        """
        clauses = []
        params: dict[str, Any] = {}

        if metro_area:
            clauses.append("LOWER(p.metro_area) LIKE :metro_area")
            params["metro_area"] = f"%{metro_area.lower()}%"

        if property_type:
            clauses.append("LOWER(p.property_type) = :property_type")
            params["property_type"] = property_type.lower()

        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        frame = pd.read_sql_query(text(query), self.engine, params=params)
        row = frame.iloc[0]

        return {
            "total_revenue": float(row["total_revenue"]),
            "total_net_income": float(row["total_net_income"]),
            "total_expenses": float(row["total_expenses"]),
        }

    def run_question(self, question: str, default_limit: int = 25) -> dict[str, Any]:
        """
        Convenience method for chat or UI use.

        Returns:
          - resolved filters
          - matching records
          - aggregate totals

        This makes the app easier to wire up while still being easy to explain.
        """
        parsed = self.parse_filters_from_question(question)
        limit = parsed.limit or default_limit

        records = self.query_properties(
            metro_area=parsed.metro_area,
            property_type=parsed.property_type,
            min_revenue=parsed.min_revenue,
            limit=limit,
        )

        totals = self.aggregate_financials(
            metro_area=parsed.metro_area,
            property_type=parsed.property_type,
        )

        return {
            "filters": {
                "metro_area": parsed.metro_area,
                "property_type": parsed.property_type,
                "min_revenue": parsed.min_revenue,
                "limit": limit,
            },
            "records": records,
            "totals": totals,
        }
