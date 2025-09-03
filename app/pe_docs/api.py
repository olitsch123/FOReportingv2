"""FastAPI endpoints for PE documents."""
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database.connection import get_db
from .storage.orm import create_pe_data_store
from .storage.ledger import create_file_ledger
from .storage.vector import get_vector_store
from .resolver import create_resolver
from .validation import validation_engine
from .classifiers import classifier
from .parsers.pdf_core import pdf_parser
from .parsers.excel import excel_parser
from .extractors.qr import qr_extractor
from .extractors.cas import cas_extractor
from .extractors.call_notice import call_notice_extractor
from .extractors.dist_notice import dist_notice_extractor
from .extractors.lpa import lpa_extractor
from .extractors.ppm import ppm_extractor
from .extractors.subscription import subscription_extractor

router = APIRouter(prefix="/pe", tags=["PE Documents"])

# Pydantic models
class RAGQuery(BaseModel):
    query: str
    fund_id: Optional[str] = None
    investor_id: Optional[str] = None
    doc_type: Optional[str] = None
    top_k: int = 5

class ProcessFileRequest(BaseModel):
    file_path: str
    org_code: str
    investor_code: str

@router.get("/documents")
async def get_documents(
    fund_id: Optional[str] = Query(None),
    investor_id: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    db: Session = Depends(get_db)
):
    """Get PE documents with optional filters."""
    where_clauses = []
    params = {}
    
    if fund_id:
        where_clauses.append("fund_id = :fund_id")
        params['fund_id'] = fund_id
    
    if investor_id:
        where_clauses.append("investor_id = :investor_id")
        params['investor_id'] = investor_id
    
    if doc_type:
        where_clauses.append("doc_type = :doc_type")
        params['doc_type'] = doc_type
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    from sqlalchemy import text
    query = text(f"""
        SELECT doc_id, org_code, investor_code, doc_type, file_name, 
               statement_date, period_end, metadata, created_at
        FROM pe_document
        WHERE {where_sql}
        ORDER BY created_at DESC
        LIMIT :limit
    """)
    
    params['limit'] = limit
    results = db.execute(query, params).fetchall()
    
    columns = ['doc_id', 'org_code', 'investor_code', 'doc_type', 'file_name',
              'statement_date', 'period_end', 'metadata', 'created_at']
    
    return [dict(zip(columns, row)) for row in results]

@router.get("/nav-bridge")
async def get_nav_bridge(
    fund_id: str,
    investor_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """Get monthly NAV bridge data."""
    pe_store = create_pe_data_store(db)
    
    try:
        bridge_data = pe_store.get_nav_bridge_view(
            fund_id=fund_id,
            investor_id=investor_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "fund_id": fund_id,
            "investor_id": investor_id,
            "periods": bridge_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving NAV bridge: {str(e)}")

@router.get("/cashflows")
async def get_cashflows(
    fund_id: str,
    investor_id: Optional[str] = Query(None),
    flow_type: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    """Get cashflows with optional filters."""
    where_clauses = ["fund_id = :fund_id"]
    params = {'fund_id': fund_id, 'limit': limit}
    
    if investor_id:
        where_clauses.append("investor_id = :investor_id")
        params['investor_id'] = investor_id
    
    if flow_type:
        where_clauses.append("flow_type = :flow_type")
        params['flow_type'] = flow_type
    
    if start_date:
        where_clauses.append("flow_date >= :start_date")
        params['start_date'] = start_date
    
    if end_date:
        where_clauses.append("flow_date <= :end_date")
        params['end_date'] = end_date
    
    where_sql = " AND ".join(where_clauses)
    
    from sqlalchemy import text
    query = text(f"""
        SELECT cashflow_id, fund_id, investor_id, flow_type, amount, 
               flow_date, due_date, payment_date, currency, doc_id, source_trace
        FROM pe_cashflow
        WHERE {where_sql}
        ORDER BY flow_date DESC
        LIMIT :limit
    """)
    
    results = db.execute(query, params).fetchall()
    
    columns = ['cashflow_id', 'fund_id', 'investor_id', 'flow_type', 'amount',
              'flow_date', 'due_date', 'payment_date', 'currency', 'doc_id', 'source_trace']
    
    return [dict(zip(columns, row)) for row in results]

@router.get("/kpis")
async def get_kpis(
    fund_id: str,
    investor_id: Optional[str] = Query(None),
    as_of_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """Get KPIs (TVPI, DPI, RVPI, IRR) for fund/investor."""
    where_clauses = ["cf.fund_id = :fund_id"]
    params = {'fund_id': fund_id}
    
    if investor_id:
        where_clauses.append("cf.investor_id = :investor_id")
        params['investor_id'] = investor_id
    
    date_filter = ""
    if as_of_date:
        date_filter = "AND cf.flow_date <= :as_of_date AND n.as_of_date <= :as_of_date"
        params['as_of_date'] = as_of_date
    
    where_sql = " AND ".join(where_clauses)
    
    from sqlalchemy import text
    query = text(f"""
        WITH cashflow_summary AS (
            SELECT 
                cf.fund_id,
                cf.investor_id,
                SUM(CASE WHEN cf.flow_type = 'CALL' THEN cf.amount ELSE 0 END) as total_calls,
                SUM(CASE WHEN cf.flow_type = 'DIST' THEN cf.amount ELSE 0 END) as total_distributions
            FROM pe_cashflow cf
            WHERE {where_sql} {date_filter}
            GROUP BY cf.fund_id, cf.investor_id
        ),
        latest_nav AS (
            SELECT DISTINCT ON (n.fund_id, n.investor_id)
                n.fund_id, n.investor_id, n.nav_amount
            FROM pe_nav_observation n
            WHERE n.fund_id = :fund_id
            {("AND n.investor_id = :investor_id" if investor_id else "")}
            {("AND n.as_of_date <= :as_of_date" if as_of_date else "")}
            ORDER BY n.fund_id, n.investor_id, n.as_of_date DESC
        )
        SELECT 
            cs.fund_id,
            cs.investor_id,
            cs.total_calls,
            cs.total_distributions,
            ln.nav_amount as current_nav,
            CASE WHEN cs.total_calls > 0 THEN cs.total_distributions / cs.total_calls ELSE 0 END as dpi,
            CASE WHEN cs.total_calls > 0 THEN ln.nav_amount / cs.total_calls ELSE 0 END as rvpi,
            CASE WHEN cs.total_calls > 0 THEN (ln.nav_amount + cs.total_distributions) / cs.total_calls ELSE 0 END as tvpi
        FROM cashflow_summary cs
        LEFT JOIN latest_nav ln ON cs.fund_id = ln.fund_id AND cs.investor_id = ln.investor_id
    """)
    
    result = db.execute(query, params).fetchone()
    
    if result:
        return {
            'fund_id': result[0],
            'investor_id': result[1],
            'total_calls': float(result[2] or 0),
            'total_distributions': float(result[3] or 0),
            'current_nav': float(result[4] or 0),
            'dpi': float(result[5] or 0),
            'rvpi': float(result[6] or 0),
            'tvpi': float(result[7] or 0),
            'as_of_date': as_of_date.isoformat() if as_of_date else None
        }
    
    return {
        'fund_id': fund_id,
        'investor_id': investor_id,
        'error': 'No data found'
    }

@router.post("/rag/query")
async def rag_query(query_data: RAGQuery, db: Session = Depends(get_db)):
    """RAG query with citations."""
    try:
        vector_store = get_vector_store()
        
        # Build filters
        filters = {}
        if query_data.fund_id:
            filters['fund_id'] = query_data.fund_id
        if query_data.investor_id:
            filters['investor_id'] = query_data.investor_id
        if query_data.doc_type:
            filters['doc_type'] = query_data.doc_type
        
        # Search vector store
        search_results = vector_store.search(
            query=query_data.query,
            filters=filters,
            top_k=query_data.top_k
        )
        
        # Format results with citations
        citations = []
        context_chunks = []
        
        for result in search_results:
            metadata = result.get('metadata', {})
            citation = {
                'doc_id': metadata.get('doc_id'),
                'page_no': metadata.get('page_no', 1),
                'snippet': result.get('text', '')[:200] + '...',
                'relevance_score': 1 - result.get('distance', 0),
                'doc_type': metadata.get('doc_type')
            }
            citations.append(citation)
            context_chunks.append(result.get('text', ''))
        
        # Generate answer using context (simplified - in production would use LLM)
        answer = f"Based on the documents, here are the key findings related to '{query_data.query}':\\n\\n"
        
        for i, chunk in enumerate(context_chunks[:3]):  # Top 3 chunks
            answer += f"{i+1}. {chunk[:300]}...\\n\\n"
        
        return {
            'query': query_data.query,
            'answer': answer,
            'citations': citations,
            'total_results': len(search_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")

@router.post("/process-file")
async def process_file_endpoint(
    request: ProcessFileRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Process a single file."""
    try:
        # Add to background processing
        background_tasks.add_task(
            handle_file,
            request.file_path,
            request.org_code,
            request.investor_code,
            db
        )
        
        return {"message": "File queued for processing", "file_path": request.file_path}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error queuing file: {str(e)}")

@router.get("/jobs")
async def get_processing_jobs(db: Session = Depends(get_db)):
    """Get processing job status."""
    ledger = create_file_ledger(db)
    
    try:
        pending_jobs = ledger.get_pending_jobs()
        stats = ledger.get_processing_stats()
        
        return {
            'stats': stats,
            'pending_jobs': pending_jobs
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving jobs: {str(e)}")

@router.post("/retry-job/{job_id}")
async def retry_job(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Retry a failed job."""
    ledger = create_file_ledger(db)
    
    try:
        # Get job details
        from sqlalchemy import text
        query = text("""
            SELECT f.source_uri, f.org_code, f.investor_code
            FROM ingestion_job j
            JOIN ingestion_file f ON j.file_id = f.file_id
            WHERE j.job_id = :job_id AND j.status = 'ERROR'
        """)
        
        result = db.execute(query, {'job_id': job_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Job not found or not in ERROR status")
        
        file_path, org_code, investor_code = result
        
        # Reset job status and reprocess
        ledger.update_job_status(job_id, 'QUEUED')
        
        background_tasks.add_task(
            handle_file,
            file_path,
            org_code,
            investor_code,
            db
        )
        
        return {"message": "Job queued for retry", "job_id": job_id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrying job: {str(e)}")

async def handle_file(file_path: str, org_code: str, investor_code: str, db: Session = None):
    """
    Main file processing handler.
    This is the entry point called by the watcher.
    """
    if db is None:
        from app.database.connection import get_db
        db = next(get_db())
    
    ledger = create_file_ledger(db)
    
    try:
        # Register file
        file_id = ledger.register_file(file_path, org_code, investor_code)
        
        # Create job
        job_id = ledger.create_job(file_id)
        
        # Update job status
        ledger.update_job_status(job_id, 'RUNNING')
        
        # Process file
        result = await _process_file_pipeline(file_path, org_code, investor_code, db)
        
        if result.get('success'):
            ledger.update_job_status(job_id, 'DONE', logs=result.get('logs', []))
        else:
            ledger.update_job_status(job_id, 'ERROR', 
                                   error_message=result.get('error', 'Unknown error'),
                                   logs=result.get('logs', []))
        
        db.commit()
        
    except Exception as e:
        if 'job_id' in locals():
            ledger.update_job_status(job_id, 'ERROR', error_message=str(e))
        db.rollback()
        raise

async def _process_file_pipeline(file_path: str, org_code: str, investor_code: str, db: Session) -> Dict[str, Any]:
    """Internal file processing pipeline."""
    logs = []
    
    try:
        # 1. Classify document
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            parsed_data = pdf_parser.parse_document(file_path)
            text_sample = parsed_data.get('text', '')[:2000]
        elif file_ext in ['.xlsx', '.xls']:
            parsed_data = excel_parser.parse_document(file_path)
            text_sample = str(parsed_data.get('structured_data', {}))[:2000]
        else:
            return {'success': False, 'error': f'Unsupported file type: {file_ext}'}
        
        doc_type, confidence = classifier.classify(Path(file_path).name, text_sample)
        logs.append(f"Classified as {doc_type} with confidence {confidence:.2f}")
        
        # 2. Extract data based on document type
        doc_metadata = {
            'doc_id': str(uuid.uuid4()),
            'org_code': org_code,
            'investor_code': investor_code,
            'file_path': file_path
        }
        
        extracted_data = {}
        
        if doc_type == 'QR':
            extracted_data = qr_extractor.extract(parsed_data, doc_metadata)
        elif doc_type == 'CAS':
            extracted_data = cas_extractor.extract(parsed_data, doc_metadata)
        elif doc_type == 'CALL':
            extracted_data = call_notice_extractor.extract(parsed_data, doc_metadata)
        elif doc_type == 'DIST':
            extracted_data = dist_notice_extractor.extract(parsed_data, doc_metadata)
        elif doc_type == 'LPA':
            extracted_data = lpa_extractor.extract(parsed_data, doc_metadata)
        elif doc_type == 'PPM':
            extracted_data = ppm_extractor.extract(parsed_data, doc_metadata)
        elif doc_type == 'SUBSCRIPTION':
            extracted_data = subscription_extractor.extract(parsed_data, doc_metadata)
        
        logs.append(f"Extracted {len(extracted_data)} data sections")
        
        # 3. Resolve entities
        resolver = create_resolver(db)
        
        fund_id = None
        investor_id = None
        
        if 'fund_metadata' in extracted_data:
            fund_id = resolver.resolve_fund(extracted_data['fund_metadata'], org_code)
            
        if 'investor_metadata' in extracted_data:
            investor_id = resolver.resolve_investor(extracted_data['investor_metadata'], investor_code, org_code)
        
        # Update doc_metadata with resolved IDs
        doc_metadata.update({
            'fund_id': fund_id,
            'investor_id': investor_id,
            'doc_type': doc_type
        })
        
        # 4. Store data
        pe_store = create_pe_data_store(db)
        
        # Store NAV observations
        nav_count = 0
        for nav_obs in extracted_data.get('nav_observations', []):
            nav_obs.update(doc_metadata)
            if resolver.validate_nav_observation(nav_obs):
                pe_store.store_nav_observation(nav_obs)
                nav_count += 1
        
        # Store cashflows
        cf_count = 0
        for cashflow in extracted_data.get('cashflows', []):
            cashflow.update(doc_metadata)
            if resolver.validate_cashflow(cashflow):
                pe_store.store_cashflow(cashflow)
                cf_count += 1
        
        logs.append(f"Stored {nav_count} NAV observations, {cf_count} cashflows")
        
        # 5. Store document metadata
        doc_record = {
            'doc_id': doc_metadata['doc_id'],
            'org_code': org_code,
            'investor_code': investor_code,
            'doc_type': doc_type,
            'file_name': Path(file_path).name,
            'file_path': file_path,
            'file_hash': ledger.calculate_file_hash(file_path),
            'file_size': Path(file_path).stat().st_size,
            'fund_id': fund_id,
            'investor_id': investor_id,
            'period_end': None,  # Could extract from data
            'statement_date': None,  # Could extract from data
            'metadata': {
                'classification_confidence': confidence,
                'extraction_summary': logs
            }
        }
        
        pe_store.store_document_metadata(doc_record)
        
        # 6. Add to vector store
        vector_store = get_vector_store()
        
        chunks = []
        for page in parsed_data.get('pages', []):
            if page.get('text', '').strip():
                chunk = {
                    'doc_id': doc_metadata['doc_id'],
                    'page_no': page['page_no'],
                    'text': page['text'],
                    'doc_type': doc_type,
                    'fund_id': fund_id,
                    'investor_id': investor_id,
                    'period_end': None  # Could extract
                }
                chunks.append(chunk)
        
        if chunks:
            vector_store.add_chunks(chunks)
            logs.append(f"Added {len(chunks)} chunks to vector store")
        
        return {
            'success': True,
            'logs': logs,
            'doc_id': doc_metadata['doc_id'],
            'nav_observations': nav_count,
            'cashflows': cf_count
        }
        
    except Exception as e:
        logs.append(f"Pipeline error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'logs': logs
        }