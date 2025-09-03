"""Chat service for natural language querying of financial data."""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
import openai

from app.database.connection import get_db_session
from app.database.models import (
    ChatSession, ChatMessage, Document, Fund, FinancialData, Investor
)
from app.services.vector_service import VectorService
from app.config import load_settings
import os

settings = load_settings()

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling natural language queries about financial data."""
    
    def __init__(self):
        """Initialize the chat service."""
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.vector_service = VectorService()
        # Use configured LLM model
        self.model = settings.get("OPENAI_LLM_MODEL", "gpt-4.1")
        self.max_tokens = settings.get("MAX_TOKENS", 4000)
        self.temperature = settings.get("TEMPERATURE", 0.1)
    
    async def create_session(self, session_name: Optional[str] = None) -> str:
        """Create a new chat session."""
        try:
            with get_db_session() as db:
                session = ChatSession(
                    session_name=session_name or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                return str(session.id)
                
        except Exception as e:
            logger.error(f"Error creating chat session: {str(e)}")
            raise
    
    async def chat(
        self, 
        session_id: str, 
        user_message: str,
        context_limit: int = 5
    ) -> Dict[str, Any]:
        """Process a chat message and return AI response."""
        try:
            # Store user message
            with get_db_session() as db:
                user_msg = ChatMessage(
                    session_id=session_id,
                    message_type="user",
                    content=user_message
                )
                db.add(user_msg)
                db.commit()
            
            # Get relevant context from documents
            context_docs = await self.vector_service.search_documents(
                query=user_message,
                limit=context_limit
            )
            
            # Get relevant financial data
            financial_context = await self._get_financial_context(user_message)
            
            # Build conversation history
            conversation_history = await self._get_conversation_history(session_id)
            
            # Generate AI response
            ai_response = await self._generate_response(
                user_message=user_message,
                context_docs=context_docs,
                financial_context=financial_context,
                conversation_history=conversation_history
            )
            
            # Store AI response
            context_document_ids = [doc['metadata'].get('document_id') for doc in context_docs if doc['metadata'].get('document_id')]
            
            with get_db_session() as db:
                ai_msg = ChatMessage(
                    session_id=session_id,
                    message_type="assistant",
                    content=ai_response,
                    context_documents=context_document_ids
                )
                db.add(ai_msg)
                db.commit()
            
            return {
                'response': ai_response,
                'context_documents': len(context_document_ids),
                'financial_data_points': len(financial_context)
            }
            
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            return {
                'response': f"I encountered an error processing your request: {str(e)}",
                'context_documents': 0,
                'financial_data_points': 0
            }
    
    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session."""
        try:
            with get_db_session() as db:
                messages = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id
                ).order_by(ChatMessage.created_at).all()
                
                return [
                    {
                        'id': str(msg.id),
                        'type': msg.message_type,
                        'content': msg.content,
                        'timestamp': msg.created_at.isoformat(),
                        'context_documents': msg.context_documents or []
                    }
                    for msg in messages
                ]
                
        except Exception as e:
            logger.error(f"Error getting session history: {str(e)}")
            return []
    
    async def _get_financial_context(self, query: str) -> List[Dict[str, Any]]:
        """Get relevant financial data based on query."""
        try:
            # Analyze query to determine what financial data might be relevant
            query_lower = query.lower()
            
            # Build dynamic SQL based on query content
            conditions = []
            params = {}
            
            # Date filtering
            if any(term in query_lower for term in ['2023', '2024', 'latest', 'recent']):
                if '2023' in query_lower:
                    conditions.append("EXTRACT(YEAR FROM fd.reporting_date) = :year")
                    params['year'] = 2023
                elif '2024' in query_lower:
                    conditions.append("EXTRACT(YEAR FROM fd.reporting_date) = :year")
                    params['year'] = 2024
                elif any(term in query_lower for term in ['latest', 'recent']):
                    conditions.append("fd.reporting_date >= CURRENT_DATE - INTERVAL '12 months'")
            
            # Fund/investor filtering
            if 'brainweb' in query_lower:
                conditions.append("i.code = :investor_code")
                params['investor_code'] = 'brainweb'
            elif 'pecunalta' in query_lower:
                conditions.append("i.code = :investor_code")
                params['investor_code'] = 'pecunalta'
            
            # Metric filtering
            metric_conditions = []
            if 'nav' in query_lower:
                metric_conditions.append("fd.nav IS NOT NULL")
            if any(term in query_lower for term in ['performance', 'return', 'irr']):
                metric_conditions.append("fd.irr IS NOT NULL")
            if 'value' in query_lower:
                metric_conditions.append("fd.total_value IS NOT NULL")
            
            if metric_conditions:
                conditions.append(f"({' OR '.join(metric_conditions)})")
            
            # Build final query
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            sql_query = f"""
            SELECT 
                fd.id,
                fd.reporting_date,
                fd.period_type,
                fd.nav,
                fd.total_value,
                fd.irr,
                fd.moic,
                fd.committed_capital,
                fd.drawn_capital,
                fd.distributed_capital,
                f.name as fund_name,
                f.code as fund_code,
                f.asset_class,
                i.name as investor_name,
                i.code as investor_code
            FROM financial_data fd
            JOIN funds f ON fd.fund_id = f.id
            JOIN investors i ON f.investor_id = i.id
            WHERE {where_clause}
            ORDER BY fd.reporting_date DESC
            LIMIT 20
            """
            
            with get_db_session() as db:
                result = db.execute(text(sql_query), params)
                rows = result.fetchall()
                
                return [
                    {
                        'id': str(row.id),
                        'reporting_date': row.reporting_date.isoformat() if row.reporting_date else None,
                        'period_type': row.period_type,
                        'nav': float(row.nav) if row.nav else None,
                        'total_value': float(row.total_value) if row.total_value else None,
                        'irr': float(row.irr) if row.irr else None,
                        'moic': float(row.moic) if row.moic else None,
                        'committed_capital': float(row.committed_capital) if row.committed_capital else None,
                        'drawn_capital': float(row.drawn_capital) if row.drawn_capital else None,
                        'distributed_capital': float(row.distributed_capital) if row.distributed_capital else None,
                        'fund_name': row.fund_name,
                        'fund_code': row.fund_code,
                        'asset_class': row.asset_class,
                        'investor_name': row.investor_name,
                        'investor_code': row.investor_code
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Error getting financial context: {str(e)}")
            return []
    
    async def _get_conversation_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history."""
        try:
            with get_db_session() as db:
                messages = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id
                ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
                
                # Reverse to get chronological order
                messages = list(reversed(messages))
                
                return [
                    {
                        'role': 'user' if msg.message_type == 'user' else 'assistant',
                        'content': msg.content
                    }
                    for msg in messages
                ]
                
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []
    
    async def _generate_response(
        self,
        user_message: str,
        context_docs: List[Dict[str, Any]],
        financial_context: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """Generate AI response using OpenAI."""
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt()
            
            # Build context information
            context_info = self._build_context_info(context_docs, financial_context)
            
            # Build messages for API call
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add conversation history
            messages.extend(conversation_history[-6:])  # Last 6 messages for context
            
            # Add current query with context
            user_prompt = f"""User Question: {user_message}

Available Context:
{context_info}

Please provide a comprehensive answer based on the available financial data and document context. If you need to make calculations or comparisons, show your work. If the data is insufficient to answer the question completely, explain what information is missing."""
            
            messages.append({"role": "user", "content": user_prompt})
            
            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return f"I encountered an error generating a response: {str(e)}"
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for financial AI assistant."""
        return """You are a sophisticated financial analyst AI assistant specializing in private equity, venture capital, and investment fund analysis. You have access to:

1. Financial documents (quarterly reports, annual reports, financial statements)
2. Structured financial data (NAV, IRR, MOIC, capital flows, etc.)
3. Fund information and investor details
4. Time series data for performance analysis

Your capabilities include:
- Analyzing fund performance metrics
- Comparing investments across time periods
- Identifying trends and patterns
- Explaining financial concepts
- Providing investment insights

Guidelines:
- Always base your responses on the provided data
- Clearly state when information is not available
- Provide specific numbers and dates when possible
- Explain financial calculations step-by-step
- Use professional financial terminology appropriately
- Highlight important trends or anomalies
- Be precise and factual in your analysis

Format your responses clearly with:
- Key findings at the top
- Supporting data and calculations
- Relevant context from documents
- Limitations or caveats when applicable"""
    
    def _build_context_info(
        self, 
        context_docs: List[Dict[str, Any]], 
        financial_context: List[Dict[str, Any]]
    ) -> str:
        """Build context information for the AI prompt."""
        context_parts = []
        
        # Add document context
        if context_docs:
            context_parts.append("=== DOCUMENT EXCERPTS ===")
            for i, doc in enumerate(context_docs[:3], 1):  # Limit to top 3 documents
                similarity = doc.get('similarity', 0)
                text = doc.get('text', '')[:500]  # Truncate long text
                metadata = doc.get('metadata', {})
                
                context_parts.append(f"Document {i} (Relevance: {similarity:.2f}):")
                context_parts.append(f"Source: {metadata.get('document_id', 'Unknown')}")
                context_parts.append(f"Content: {text}...")
                context_parts.append("")
        
        # Add financial data context
        if financial_context:
            context_parts.append("=== FINANCIAL DATA ===")
            
            # Group by fund for better organization
            funds_data = {}
            for item in financial_context:
                fund_key = f"{item['investor_code']} - {item['fund_name']}"
                if fund_key not in funds_data:
                    funds_data[fund_key] = []
                funds_data[fund_key].append(item)
            
            for fund_key, fund_items in funds_data.items():
                context_parts.append(f"Fund: {fund_key}")
                
                for item in fund_items[:5]:  # Limit to 5 data points per fund
                    date = item.get('reporting_date', 'Unknown')[:10] if item.get('reporting_date') else 'Unknown'
                    period = item.get('period_type', 'Unknown')
                    
                    data_points = []
                    if item.get('nav'):
                        data_points.append(f"NAV: €{item['nav']:,.0f}")
                    if item.get('total_value'):
                        data_points.append(f"Total Value: €{item['total_value']:,.0f}")
                    if item.get('irr'):
                        data_points.append(f"IRR: {item['irr']:.1f}%")
                    if item.get('moic'):
                        data_points.append(f"MOIC: {item['moic']:.2f}x")
                    
                    if data_points:
                        context_parts.append(f"  {date} ({period}): {', '.join(data_points)}")
                
                context_parts.append("")
        
        return "\n".join(context_parts) if context_parts else "No specific context available."