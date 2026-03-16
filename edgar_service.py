# -*- coding: utf-8 -*-
"""edgar_service.ipynb

Original file is located at
    https://colab.research.google.com/drive/17YC51K-REa1-ZDg64ON_8kEHYeHyoVUj
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import time
import requests
import json

EDGAR_TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "net_income": ["NetIncomeLoss"],
    "operating_expenses": ["OperatingExpenses"],
}

ALLOWED_FORMS = {"10-K", "10-Q"}  # strict on purpose for demo clarity
UNIT = "USD"


@dataclass(frozen=True)
class EdgarMetricRecord:
    metric: str
    form: str
    period_end: str
    filed: str
    value: float
    tag: str  # which XBRL tag was used


class EdgarService:
    """
    Pull SEC XBRL company facts and extract a few standard metrics.

    Design choices:
      - Uses SEC companyfacts JSON instead of scraping filings.
      - Keeps logic simple and explainable for interview/demo use.
      - Uses a short TTL cache to avoid repeated SEC calls during Streamlit reruns.
      - Returns explicit errors instead of inventing fallback financial values.
    """

    def __init__(self, cik: str, user_agent: str, timeout_s: int = 20, ttl_s: int = 900):
        self.cik = cik.zfill(10)
        self.user_agent = user_agent.strip()
        self.timeout_s = timeout_s
        self.ttl_s = ttl_s
        self._cache: Optional[Tuple[float, Dict[str, Any]]] = None  # (fetched_at, json)

        if len(self.user_agent) < 8 or "@" not in self.user_agent:
            raise ValueError(
                "User-Agent must be descriptive and include contact info, "
                "for example: 'Jane Doe jane.doe@email.com'"
            )

    def _fetch_company_facts(self) -> Dict[str, Any]:
        """Fetch companyfacts JSON from SEC, using a simple TTL cache."""
        if self._cache is not None:
            fetched_at, cached = self._cache
            if time.time() - fetched_at < self.ttl_s:
                return cached

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{self.cik}.json"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }

        resp = requests.get(url, headers=headers, timeout=self.timeout_s)
        resp.raise_for_status()

        data = resp.json()
        self._cache = (time.time(), data)
        return data

    @staticmethod
    def _iter_usd_facts(facts: Dict[str, Any], tag: str) -> List[Dict[str, Any]]:
        """Return raw fact records for a given XBRL tag in USD."""
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        node = us_gaap.get(tag) or {}
        return (node.get("units", {}) or {}).get(UNIT, []) or []

    @staticmethod
    def _clean_items(metric_name: str, tag: str, items: List[Dict[str, Any]]) -> List[EdgarMetricRecord]:
        out: List[EdgarMetricRecord] = []

        for it in items:
            form = (it.get("form") or "").strip()
            if form not in ALLOWED_FORMS:
                continue

            end = (it.get("end") or "").strip()
            filed = (it.get("filed") or "").strip()
            val = it.get("val")

            if not end or not filed or val is None:
                continue

            try:
                out.append(
                    EdgarMetricRecord(
                        metric=metric_name,
                        form=form,
                        period_end=end,
                        filed=filed,
                        value=float(val),
                        tag=tag,
                    )
                )
            except (TypeError, ValueError):
                continue

        out.sort(key=lambda r: (r.filed, r.period_end), reverse=True)
        return out

    @staticmethod
    def _dedupe(records: List[EdgarMetricRecord]) -> List[EdgarMetricRecord]:
        seen = set()
        deduped: List[EdgarMetricRecord] = []

        for r in records:
            key = (r.form, r.period_end, r.metric)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)

        return deduped

    def _extract_metric(
        self,
        facts: Dict[str, Any],
        metric_name: str,
        tags: List[str],
        max_items: int,
    ) -> List[EdgarMetricRecord]:
        for tag in tags:
            items = self._iter_usd_facts(facts, tag)
            if not items:
                continue

            cleaned = self._clean_items(metric_name, tag, items)
            if not cleaned:
                continue

            cleaned = self._dedupe(cleaned)
            return cleaned[:max_items]

        return []

    def get_recent_financial_metrics(self, max_items_each: int = 6) -> Dict[str, Any]:
        try:
            facts = self._fetch_company_facts()
            metrics = {
                metric: self._extract_metric(facts, metric, tags, max_items_each)
                for metric, tags in EDGAR_TAGS.items()
            }
            return {
                "status": "ok",
                "cik": self.cik,
                "metrics": metrics,
                "error": None,
            }
        except Exception as e:
            return {
                "status": "error",
                "cik": self.cik,
                "metrics": {k: [] for k in EDGAR_TAGS.keys()},
                "error": f"{type(e).__name__}: {e}",
            }
