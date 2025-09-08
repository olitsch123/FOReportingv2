"""PE Analytics API endpoints - NAV bridge, KPIs, and performance metrics."""

from datetime import date
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.pe_docs.storage.orm import PEStorageORM

router = APIRouter(tags=["PE Analytics"])


class NAVBridgeResponse(BaseModel):
    """NAV bridge analysis response."""
    fund_id: str
    analysis_date: date
    nav_sources: List[Dict]
    reconciliation_status: str
    discrepancies: List[Dict]


class FundKPIs(BaseModel):
    """Fund KPI metrics."""
    fund_id: str
    as_of_date: date
    nav: Optional[float] = None
    irr: Optional[float] = None
    moic: Optional[float] = None
    dpi: Optional[float] = None
    tvpi: Optional[float] = None
    called_percentage: Optional[float] = None


@router.get("/nav-bridge", response_model=List[NAVBridgeResponse])
async def get_nav_bridge(
    fund_id: Optional[str] = Query(None),
    investor_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """NAV bridge analysis - reconcile NAV across different document types.
    
    This endpoint analyzes NAV consistency across:
    - Capital account statements
    - Quarterly reports  
    - Financial statements
    """
    try:
        storage = PEStorageORM(db)
        
        # Get all funds or filter by criteria
        if fund_id:
            fund_ids = [fund_id]
        elif investor_code:
            # Get funds for investor
            funds = storage.get_funds_by_investor(investor_code)
            fund_ids = [str(fund.id) for fund in funds]
        else:
            # Get all funds
            funds = storage.get_all_funds()
            fund_ids = [str(fund.id) for fund in funds[:10]]  # Limit for performance
        
        nav_analyses = []
        
        for fid in fund_ids:
            try:
                # Get NAV data from different sources
                capital_accounts = storage.get_capital_account_series(fid)
                quarterly_reports = storage.get_quarterly_reports(fid)
                
                # Perform NAV reconciliation
                nav_sources = []
                discrepancies = []
                
                # Capital account NAVs
                for ca in capital_accounts:
                    nav_sources.append({
                        "source": "capital_account",
                        "period": ca.get("period_label"),
                        "nav": ca.get("ending_balance"),
                        "date": ca.get("as_of_date")
                    })
                
                # Quarterly report NAVs
                for qr in quarterly_reports:
                    nav_sources.append({
                        "source": "quarterly_report", 
                        "period": qr.get("period_label"),
                        "nav": qr.get("fund_nav"),
                        "date": qr.get("report_date")
                    })
                
                # Simple reconciliation logic
                reconciliation_status = "clean"
                if len(nav_sources) > 1:
                    # Check for significant discrepancies
                    navs = [src["nav"] for src in nav_sources if src["nav"]]
                    if navs:
                        max_nav = max(navs)
                        min_nav = min(navs)
                        if max_nav > 0 and (max_nav - min_nav) / max_nav > 0.05:  # 5% threshold
                            reconciliation_status = "discrepancies"
                            discrepancies.append({
                                "type": "nav_variance",
                                "max_nav": max_nav,
                                "min_nav": min_nav,
                                "variance_pct": ((max_nav - min_nav) / max_nav) * 100
                            })
                
                nav_analyses.append(NAVBridgeResponse(
                    fund_id=fid,
                    analysis_date=date.today(),
                    nav_sources=nav_sources,
                    reconciliation_status=reconciliation_status,
                    discrepancies=discrepancies
                ))
                
            except Exception as fund_error:
                # Log but continue with other funds
                nav_analyses.append(NAVBridgeResponse(
                    fund_id=fid,
                    analysis_date=date.today(),
                    nav_sources=[],
                    reconciliation_status="error",
                    discrepancies=[{"type": "processing_error", "message": str(fund_error)}]
                ))
        
        return nav_analyses
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NAV bridge analysis failed: {str(e)}")


@router.get("/kpis", response_model=List[FundKPIs])
async def get_fund_kpis(
    fund_id: Optional[str] = Query(None),
    investor_code: Optional[str] = Query(None), 
    as_of_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Get key performance indicators for funds.
    
    Returns latest KPIs including NAV, IRR, MOIC, DPI, TVPI.
    """
    try:
        storage = PEStorageORM(db)
        
        # Get target funds
        if fund_id:
            fund_ids = [fund_id]
        elif investor_code:
            funds = storage.get_funds_by_investor(investor_code)
            fund_ids = [str(fund.id) for fund in funds]
        else:
            funds = storage.get_all_funds()
            fund_ids = [str(fund.id) for fund in funds[:20]]  # Limit for performance
        
        kpis_list = []
        
        for fid in fund_ids:
            try:
                # Get latest capital account data
                capital_series = storage.get_capital_account_series(fid)
                
                if capital_series:
                    # Get most recent data
                    latest = capital_series[-1]  # Assuming sorted by date
                    
                    # Calculate performance metrics
                    total_contributions = latest.get("total_contributions_itd", 0) or latest.get("drawn_commitment", 0)
                    total_distributions = latest.get("total_distributions_itd", 0) or 0
                    current_nav = latest.get("ending_balance", 0) or latest.get("current_nav", 0)
                    
                    # Calculate metrics
                    moic = None
                    dpi = None
                    tvpi = None
                    called_pct = None
                    
                    if total_contributions and total_contributions > 0:
                        total_value = total_distributions + current_nav
                        moic = total_value / total_contributions
                        dpi = total_distributions / total_contributions
                        tvpi = moic  # TVPI = MOIC in this context
                    
                    total_commitment = latest.get("total_commitment", 0)
                    if total_commitment and total_commitment > 0:
                        called_pct = (total_contributions / total_commitment) * 100
                    
                    kpis = FundKPIs(
                        fund_id=fid,
                        as_of_date=latest.get("as_of_date") or date.today(),
                        nav=current_nav,
                        irr=latest.get("irr"),  # From document if available
                        moic=moic,
                        dpi=dpi, 
                        tvpi=tvpi,
                        called_percentage=called_pct
                    )
                    
                    kpis_list.append(kpis)
                    
            except Exception as fund_error:
                # Continue with other funds, but log the error
                continue
        
        return kpis_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching fund KPIs: {str(e)}")


@router.get("/capital-accounts/{investor_code}")
async def get_capital_accounts(
    investor_code: str,
    fund_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get capital account data for an investor.
    
    Returns capital account statements and balances.
    """
    try:
        storage = PEStorageORM(db)
        
        # Get investor funds
        if fund_id:
            fund_ids = [fund_id]
        else:
            funds = storage.get_funds_by_investor(investor_code)
            fund_ids = [str(fund.id) for fund in funds]
        
        capital_accounts = {}
        
        for fid in fund_ids:
            try:
                series = storage.get_capital_account_series(fid)
                if series:
                    capital_accounts[fid] = {
                        "fund_id": fid,
                        "series": series,
                        "latest_balance": series[-1].get("ending_balance") if series else None,
                        "total_commitment": series[-1].get("total_commitment") if series else None,
                        "unfunded_commitment": series[-1].get("unfunded_commitment") if series else None
                    }
                    
            except Exception as fund_error:
                capital_accounts[fid] = {
                    "fund_id": fid,
                    "error": str(fund_error),
                    "series": []
                }
        
        return {
            "investor_code": investor_code,
            "capital_accounts": capital_accounts,
            "summary": {
                "total_funds": len(fund_ids),
                "funds_with_data": len([ca for ca in capital_accounts.values() if ca.get("series")]),
                "total_nav": sum(
                    ca.get("latest_balance", 0) or 0 
                    for ca in capital_accounts.values() 
                    if ca.get("latest_balance")
                )
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching capital accounts: {str(e)}")


@router.get("/cashflows")
async def get_fund_cashflows(
    fund_id: Optional[str] = Query(None),
    investor_code: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """Get cashflow data for funds (contributions and distributions)."""
    try:
        storage = PEStorageORM(db)
        
        # Get target funds
        if fund_id:
            fund_ids = [fund_id]
        elif investor_code:
            funds = storage.get_funds_by_investor(investor_code)
            fund_ids = [str(fund.id) for fund in funds]
        else:
            funds = storage.get_all_funds()
            fund_ids = [str(fund.id) for fund in funds[:10]]
        
        cashflows = {}
        
        for fid in fund_ids:
            try:
                # Get capital account series for cashflow analysis
                series = storage.get_capital_account_series(fid)
                
                if series:
                    fund_cashflows = []
                    
                    for period in series:
                        period_data = {
                            "period": period.get("period_label"),
                            "as_of_date": period.get("as_of_date"),
                            "contributions": period.get("contributions_period", 0),
                            "distributions": period.get("distributions_period", 0),
                            "net_cashflow": (period.get("contributions_period", 0) or 0) - (period.get("distributions_period", 0) or 0),
                            "management_fees": period.get("management_fees_period", 0)
                        }
                        
                        # Apply date filters if specified
                        if start_date or end_date:
                            period_date = period.get("as_of_date")
                            if period_date:
                                if isinstance(period_date, str):
                                    from datetime import datetime
                                    period_date = datetime.fromisoformat(period_date).date()
                                
                                if start_date and period_date < start_date:
                                    continue
                                if end_date and period_date > end_date:
                                    continue
                        
                        fund_cashflows.append(period_data)
                    
                    cashflows[fid] = {
                        "fund_id": fid,
                        "cashflows": fund_cashflows,
                        "summary": {
                            "total_contributions": sum(cf.get("contributions", 0) for cf in fund_cashflows),
                            "total_distributions": sum(cf.get("distributions", 0) for cf in fund_cashflows),
                            "net_cashflow": sum(cf.get("net_cashflow", 0) for cf in fund_cashflows),
                            "periods_count": len(fund_cashflows)
                        }
                    }
                    
            except Exception as fund_error:
                cashflows[fid] = {
                    "fund_id": fid,
                    "error": str(fund_error),
                    "cashflows": []
                }
        
        return {
            "cashflows": cashflows,
            "filters": {
                "fund_id": fund_id,
                "investor_code": investor_code,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            },
            "summary": {
                "funds_analyzed": len(fund_ids),
                "total_periods": sum(
                    len(cf.get("cashflows", [])) 
                    for cf in cashflows.values() 
                    if isinstance(cf.get("cashflows"), list)
                )
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cashflows: {str(e)}")


@router.get("/capital-account-series/{fund_id}")
async def get_capital_account_series(
    fund_id: str,
    db: Session = Depends(get_db)
):
    """Get capital account time series for a specific fund.
    
    Returns complete capital account history with analytics.
    """
    try:
        storage = PEStorageORM(db)
        
        # Get capital account series
        series = storage.get_capital_account_series(fund_id)
        
        if not series:
            raise HTTPException(status_code=404, detail="No capital account data found for fund")
        
        # Calculate analytics
        analytics = {
            "periods_count": len(series),
            "date_range": {
                "start": min(item.get("as_of_date") for item in series if item.get("as_of_date")),
                "end": max(item.get("as_of_date") for item in series if item.get("as_of_date"))
            },
            "balance_trend": {
                "initial": series[0].get("beginning_balance") if series else None,
                "final": series[-1].get("ending_balance") if series else None,
                "growth": None
            },
            "cashflow_summary": {
                "total_contributions": sum(item.get("contributions_period", 0) or 0 for item in series),
                "total_distributions": sum(item.get("distributions_period", 0) or 0 for item in series),
                "total_fees": sum(item.get("management_fees_period", 0) or 0 for item in series)
            }
        }
        
        # Calculate growth if we have data
        if analytics["balance_trend"]["initial"] and analytics["balance_trend"]["final"]:
            initial = analytics["balance_trend"]["initial"]
            final = analytics["balance_trend"]["final"]
            if initial > 0:
                analytics["balance_trend"]["growth"] = ((final / initial) - 1) * 100
        
        return {
            "fund_id": fund_id,
            "series": series,
            "analytics": analytics,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching capital account series: {str(e)}")