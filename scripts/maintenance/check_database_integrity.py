"""Comprehensive database integrity check."""

import json

from sqlalchemy import text

from app.database.connection import get_db_session


def check_database_integrity():
    """Check all database tables and their relationships."""
    
    with get_db_session() as db:
        print("🔍 DATABASE INTEGRITY CHECK")
        print("=" * 50)
        
        # 1. Check all PE tables
        pe_tables = [
            'pe_investor',
            'pe_fund_master', 
            'pe_document',
            'pe_quarterly_report',
            'pe_capital_account',
            'pe_reconciliation_log'
        ]
        
        # 2. Check regular tables
        regular_tables = [
            'investor',
            'fund',
            'document',
            'financial_data',
            'document_tracker',
            'alembic_version'
        ]
        
        all_tables = pe_tables + regular_tables
        missing_tables = []
        
        print("\n📊 TABLE EXISTENCE CHECK:")
        for table in all_tables:
            result = db.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table}'
                )
            """)).scalar()
            
            status = "✅" if result else "❌"
            print(f"{status} {table}")
            if not result:
                missing_tables.append(table)
        
        # 3. Check critical columns in PE tables
        print("\n🔧 CRITICAL COLUMNS CHECK:")
        
        # Check pe_document columns
        doc_cols = db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'pe_document'
            ORDER BY ordinal_position
        """)).fetchall()
        
        print("\npe_document columns:")
        required_doc_cols = ['doc_id', 'doc_type', 'file_path', 'investor_id', 
                             'fund_id', 'processing_status', 'embedding_status', 
                             'chunk_count', 'embedding_error']
        for col in doc_cols:
            marker = "✓" if col.column_name in required_doc_cols else " "
            print(f"  {marker} {col.column_name}: {col.data_type}")
        
        # Check for missing columns
        existing_cols = [col.column_name for col in doc_cols]
        missing_cols = [col for col in required_doc_cols if col not in existing_cols]
        if missing_cols:
            print(f"\n❌ Missing columns in pe_document: {missing_cols}")
        
        # 4. Check document_tracker columns
        tracker_cols = db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'document_tracker'
            ORDER BY ordinal_position
        """)).fetchall()
        
        print("\ndocument_tracker columns:")
        required_tracker_cols = ['file_hash', 'file_path', 'processing_status', 
                                 'extracted_records', 'doc_metadata']
        for col in tracker_cols:
            marker = "✓" if col.column_name in required_tracker_cols else " "
            print(f"  {marker} {col.column_name}: {col.data_type}")
        
        # 5. Check row counts
        print("\n📈 DATA STATISTICS:")
        for table in all_tables:
            if table not in missing_tables:
                count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                if count > 0:
                    print(f"  {table}: {count} rows")
        
        # 6. Check foreign key relationships
        print("\n🔗 FOREIGN KEY RELATIONSHIPS:")
        fk_query = text("""
            SELECT
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name 
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            ORDER BY tc.table_name
        """)
        
        fks = db.execute(fk_query).fetchall()
        for fk in fks:
            print(f"  {fk.table_name}.{fk.column_name} → {fk.foreign_table_name}.{fk.foreign_column_name}")
        
        # 7. Check for data consistency issues
        print("\n⚠️  DATA CONSISTENCY CHECKS:")
        
        # Check for documents without investors
        orphan_docs = db.execute(text("""
            SELECT COUNT(*) FROM document d
            WHERE NOT EXISTS (
                SELECT 1 FROM investor i WHERE i.id = d.investor_id
            )
        """)).scalar()
        
        if orphan_docs > 0:
            print(f"  ❌ {orphan_docs} documents without valid investor")
        else:
            print(f"  ✅ All documents have valid investors")
        
        # Check for pe_documents without pe_investor
        if 'pe_document' not in missing_tables:
            pe_orphan_docs = db.execute(text("""
                SELECT COUNT(*) FROM pe_document pd
                WHERE investor_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM pe_investor pi WHERE pi.investor_id = pd.investor_id
                )
            """)).scalar()
            
            if pe_orphan_docs > 0:
                print(f"  ❌ {pe_orphan_docs} PE documents without valid PE investor")
            else:
                print(f"  ✅ All PE documents have valid PE investors")
        
        # Check embedding status
        if 'pe_document' not in missing_tables:
            embedding_stats = db.execute(text("""
                SELECT 
                    embedding_status,
                    COUNT(*) as count
                FROM pe_document
                WHERE processing_status = 'completed'
                GROUP BY embedding_status
            """)).fetchall()
            
            print("\n📊 EMBEDDING STATUS:")
            for stat in embedding_stats:
                status = stat.embedding_status or 'NULL'
                print(f"  {status}: {stat.count} documents")
        
        # 8. Check latest migrations
        print("\n🔄 ALEMBIC MIGRATIONS:")
        migrations = db.execute(text("""
            SELECT version_num 
            FROM alembic_version 
            ORDER BY version_num
        """)).fetchall()
        
        for m in migrations:
            print(f"  ✓ {m.version_num}")
        
        print("\n" + "=" * 50)
        print("✅ DATABASE INTEGRITY CHECK COMPLETE")
        
        if missing_tables:
            print(f"\n⚠️  WARNING: Missing tables: {missing_tables}")
            print("Run alembic migrations to create missing tables.")
        
        return len(missing_tables) == 0

if __name__ == "__main__":
    check_database_integrity()