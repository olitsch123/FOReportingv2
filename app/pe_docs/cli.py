"""CLI tools for PE documents."""
import click
from typing import List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from app.database.connection import get_db
from .storage.ledger import create_file_ledger
from .api import handle_file
from app.config import settings

@click.group()
def pe_cli():
    """PE Documents CLI tools."""
    pass

@pe_cli.command()
@click.option('--org-code', required=True, help='Organization code')
@click.option('--investor-code', required=True, help='Investor code')
@click.option('--path', required=True, help='Directory or file path to process')
@click.option('--dry-run', is_flag=True, help='Show files that would be processed')
def backfill(org_code: str, investor_code: str, path: str, dry_run: bool):
    """Backfill processing for a directory or file."""
    path_obj = Path(path)
    
    if not path_obj.exists():
        click.echo(f"Error: Path does not exist: {path}")
        return
    
    db = next(get_db())
    ledger = create_file_ledger(db)
    
    try:
        if path_obj.is_file():
            files_to_process = [str(path_obj)]
        else:
            files_to_process = ledger.scan_directory(str(path_obj), org_code, investor_code)
        
        click.echo(f"Found {len(files_to_process)} new files to process")
        
        if dry_run:
            for file_path in files_to_process:
                click.echo(f"  Would process: {file_path}")
            return
        
        # Process files
        for i, file_path in enumerate(files_to_process, 1):
            click.echo(f"Processing {i}/{len(files_to_process)}: {Path(file_path).name}")
            
            try:
                import asyncio
                result = asyncio.run(handle_file(file_path, org_code, investor_code, db))
                click.echo(f"  ✓ Success")
            except Exception as e:
                click.echo(f"  ✗ Error: {str(e)}")
                continue
        
        db.commit()
        click.echo("Backfill completed")
        
    except Exception as e:
        db.rollback()
        click.echo(f"Error during backfill: {str(e)}")
    finally:
        db.close()

@pe_cli.command()
def scan_watch_paths():
    """Scan configured watch paths for new files."""
    db = next(get_db())
    ledger = create_file_ledger(db)
    
    try:
        investor1_path = settings.get('INVESTOR1_PATH')
        investor2_path = settings.get('INVESTOR2_PATH')
        
        total_new_files = 0
        
        if investor1_path:
            click.echo(f"Scanning INVESTOR1_PATH: {investor1_path}")
            new_files = ledger.scan_directory(investor1_path, "brainweb", "brainweb")
            click.echo(f"  Found {len(new_files)} new files")
            total_new_files += len(new_files)
        
        if investor2_path:
            click.echo(f"Scanning INVESTOR2_PATH: {investor2_path}")
            new_files = ledger.scan_directory(investor2_path, "pecunalta", "pecunalta")
            click.echo(f"  Found {len(new_files)} new files")
            total_new_files += len(new_files)
        
        click.echo(f"Total new files across all paths: {total_new_files}")
        
    except Exception as e:
        click.echo(f"Error scanning paths: {str(e)}")
    finally:
        db.close()

@pe_cli.command()
@click.option('--fund-id', required=True, help='Fund ID')
@click.option('--investor-id', help='Investor ID (optional)')
def show_nav_bridge(fund_id: str, investor_id: Optional[str]):
    """Show NAV bridge for fund/investor."""
    db = next(get_db())
    
    try:
        from .storage.orm import create_pe_data_store
        pe_store = create_pe_data_store(db)
        
        bridge_data = pe_store.get_nav_bridge_view(fund_id, investor_id)
        
        if not bridge_data:
            click.echo("No NAV bridge data found")
            return
        
        click.echo(f"NAV Bridge for Fund {fund_id}" + (f", Investor {investor_id}" if investor_id else ""))
        click.echo("-" * 80)
        click.echo(f"{'Period':<12} {'Nav Begin':<12} {'Contributions':<12} {'Distributions':<12} {'Fees':<8} {'P&L':<12} {'Nav End':<12}")
        click.echo("-" * 80)
        
        for period in bridge_data:
            click.echo(f"{str(period['period_end']):<12} "
                      f"{period['nav_begin'] or 0:<12.0f} "
                      f"{period['contributions'] or 0:<12.0f} "
                      f"{period['distributions'] or 0:<12.0f} "
                      f"{period['fees'] or 0:<8.0f} "
                      f"{period['pnl'] or 0:<12.0f} "
                      f"{period['nav_end'] or 0:<12.0f}")
    
    except Exception as e:
        click.echo(f"Error retrieving NAV bridge: {str(e)}")
    finally:
        db.close()

@pe_cli.command()
def stats():
    """Show processing statistics."""
    db = next(get_db())
    ledger = create_file_ledger(db)
    
    try:
        stats = ledger.get_processing_stats()
        
        click.echo("Processing Statistics")
        click.echo("-" * 30)
        click.echo(f"Total files: {stats['total_files']}")
        click.echo(f"Processed: {stats['processed']}")
        click.echo(f"Queued: {stats['queued']}")
        click.echo(f"Errors: {stats['errors']}")
        click.echo(f"Running: {stats['running']}")
        
        if stats['errors'] > 0:
            click.echo("\\nError jobs:")
            pending_jobs = ledger.get_pending_jobs()
            for job in pending_jobs:
                if job['status'] == 'ERROR':
                    click.echo(f"  Job {job['job_id']}: {job['file_name']} - {job['error_message']}")
    
    except Exception as e:
        click.echo(f"Error retrieving stats: {str(e)}")
    finally:
        db.close()

if __name__ == '__main__':
    pe_cli()