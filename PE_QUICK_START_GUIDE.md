# PE Features Quick Start Guide

## 🚀 Getting Started with PE Document Processing

### 1. Ensure System is Running

```bash
# Start all services
docker-compose up -d

# Verify services are healthy
docker-compose ps
```

### 2. Process Your First PE Document

Place PE documents in the watched folders:
- `data/investor1/` - For investor 1 documents
- `data/investor2/` - For investor 2 documents

Supported document types:
- Capital Account Statements
- Quarterly Reports
- Capital Call Notices
- Distribution Notices

### 3. Check Processing Status

```bash
# View processing logs
docker-compose logs -f backend

# Check document in database
curl http://localhost:8000/documents
```

### 4. Access Capital Account Time Series

```bash
# Get capital account data for a fund
curl "http://localhost:8000/pe/capital-account-series/{fund_id}"

# With filters
curl "http://localhost:8000/pe/capital-account-series/{fund_id}?start_date=2023-01-01&frequency=quarterly"

# With forecast
curl "http://localhost:8000/pe/capital-account-series/{fund_id}?include_forecast=true"
```

### 5. Run Reconciliation

```bash
# Trigger reconciliation
curl -X POST "http://localhost:8000/pe/reconcile/{fund_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "as_of_date": "2023-12-31",
    "reconciliation_types": ["nav", "cashflow", "performance", "commitment"]
  }'
```

### 6. Review Extraction Audit

```bash
# Get extraction audit for a document
curl "http://localhost:8000/pe/extraction-audit/{doc_id}"

# Apply manual corrections
curl -X POST "http://localhost:8000/pe/manual-override/{doc_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "field_overrides": {
      "ending_balance": 40700000,
      "total_commitment": 50000000
    },
    "reviewer_id": "user@example.com",
    "override_reason": "Corrected OCR error"
  }'
```

## 📊 Using the Frontend Dashboard

Access the Streamlit dashboard at: http://localhost:8501

Key features:
- Document upload and status
- Capital account visualization
- Extraction review interface
- Reconciliation results

## 🔍 API Endpoints Reference

### PE-Specific Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/pe/capital-account-series/{fund_id}` | GET | Time-series capital account data |
| `/pe/reconcile/{fund_id}` | POST | Trigger reconciliation |
| `/pe/extraction-audit/{doc_id}` | GET | View extraction audit trail |
| `/pe/manual-override/{doc_id}` | POST | Apply manual corrections |
| `/pe/rag` | POST | PE-specific document search |

### Query Parameters

**Capital Account Series:**
- `investor_id`: Filter by specific investor
- `start_date`: Start date for series
- `end_date`: End date for series
- `frequency`: monthly, quarterly, annual
- `include_forecast`: Include forecast data

## 🛠️ Troubleshooting

### Documents Not Processing
1. Check file watcher is running: `docker-compose logs watcher`
2. Verify file permissions in data folders
3. Check document format is supported

### Extraction Issues
1. Review extraction audit: `/pe/extraction-audit/{doc_id}`
2. Check confidence scores
3. Apply manual overrides if needed

### Reconciliation Failures
1. Check reconciliation log in database
2. Review specific reconciliation type that failed
3. Verify data completeness

## 📈 Best Practices

1. **Document Organization**
   - Use consistent file naming
   - Organize by fund/investor
   - Keep documents in standard formats

2. **Data Quality**
   - Review low-confidence extractions
   - Run reconciliation regularly
   - Monitor validation errors

3. **Performance**
   - Process documents in batches
   - Use date filters for large datasets
   - Archive old documents

## 🔐 Security Notes

- Always use environment variables for credentials
- Restrict access to manual override endpoints
- Maintain audit trail for compliance
- Regular backup of PostgreSQL database

## 📞 Getting Help

1. Check logs: `docker-compose logs [service]`
2. Review API documentation: http://localhost:8000/docs
3. Check extraction confidence scores
4. Review reconciliation results

The PE document processing system is now fully operational and ready for production use!