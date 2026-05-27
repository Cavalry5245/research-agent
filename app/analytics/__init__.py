"""Analytics module: lightweight event collection, analysis, and visualization for Phase 2."""

from app.analytics.data_collector import (
    AnalyticsCollector,
    AnalyticsEvent,
    get_collector,
)

__all__ = ["AnalyticsCollector", "AnalyticsEvent", "get_collector"]
