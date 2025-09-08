"""Prometheus metrics instrumentation for FOReporting v2."""

import logging

from fastapi import FastAPI
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_fastapi_instrumentator import Instrumentator, metrics

logger = logging.getLogger(__name__)

# Custom business metrics
DOCUMENTS_PROCESSED = Counter(
    'documents_processed_total',
    'Total number of documents processed',
    ['investor_code', 'document_type', 'status']
)

EXTRACTION_CONFIDENCE = Histogram(
    'extraction_confidence_score',
    'Distribution of extraction confidence scores',
    ['document_type', 'extraction_method']
)

PROCESSING_DURATION = Histogram(
    'document_processing_duration_seconds',
    'Time taken to process documents',
    ['document_type', 'file_size_category']
)

RECONCILIATION_DISCREPANCIES = Counter(
    'reconciliation_discrepancies_total',
    'Number of reconciliation discrepancies found',
    ['fund_id', 'metric_type', 'severity']
)

ACTIVE_FUNDS = Gauge(
    'active_funds_count',
    'Number of active funds being monitored'
)

VECTOR_STORE_OPERATIONS = Counter(
    'vector_store_operations_total',
    'Vector store operations',
    ['operation', 'backend', 'status']
)

FILE_WATCHER_STATUS = Gauge(
    'file_watcher_status',
    'File watcher status (1=running, 0=stopped)'
)

OPENAI_API_CALLS = Counter(
    'openai_api_calls_total',
    'OpenAI API calls',
    ['operation', 'model', 'status']
)

SYSTEM_INFO = Info(
    'forreporting_system_info',
    'System information and version'
)


def setup_metrics(app: FastAPI) -> Instrumentator:
    """Setup Prometheus metrics for the FastAPI app."""
    
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=[".*admin.*", "/metrics"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="forreporting_requests_inprogress",
        inprogress_labels=True,
    )
    
    # Add custom metrics
    instrumentator.add(
        metrics.request_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
            metric_namespace="forreporting",
            metric_subsystem="requests",
        )
    ).add(
        metrics.response_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
            metric_namespace="forreporting",
            metric_subsystem="requests",
        )
    ).add(
        metrics.latency(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
            metric_namespace="forreporting",
            metric_subsystem="requests",
        )
    ).add(
        metrics.requests(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
            metric_namespace="forreporting",
            metric_subsystem="requests",
        )
    )
    
    # Instrument the app
    instrumentator.instrument(app)
    
    # Expose metrics endpoint
    instrumentator.expose(app, endpoint="/metrics")
    
    logger.info("Prometheus metrics configured and exposed at /metrics")
    return instrumentator