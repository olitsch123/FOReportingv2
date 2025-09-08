"""Sample document content for testing - using actual test documents from data/test_documents/."""

# Actual test document content from data/test_documents/sample_capital_account.txt
SAMPLE_CAPITAL_ACCOUNT_PDF = """CAPITAL ACCOUNT STATEMENT

Fund Name: Astorg VII
Fund Manager: Astorg Partners
Investor: BrainWeb Investment GmbH
Investor ID: BWI-001

Statement Date: December 31, 2023
Period: Q4 2023

CAPITAL ACCOUNT SUMMARY

Beginning Balance (October 1, 2023):             $35,000,000.00

ACTIVITY DURING PERIOD

Capital Contributions:
  Capital Call #12 (November 15, 2023)           $5,000,000.00
  Total Contributions This Period                $5,000,000.00

Distributions:
  Distribution - Return of Capital               ($2,000,000.00)
  Distribution - Realized Gains                  ($1,500,000.00)
  Distribution - Income                            ($500,000.00)
  Total Distributions This Period                ($4,000,000.00)

Management Fees:
  Q4 2023 Management Fee (0.5%)                   ($250,000.00)
  
Partnership Expenses:
  Fund Administration                               ($30,000.00)
  Audit & Tax Preparation                           ($20,000.00)
  Total Partnership Expenses                        ($50,000.00)

Investment Activity:
  Realized Gain/(Loss)                           $1,500,000.00
  Unrealized Gain/(Loss)                         $3,000,000.00
  Total Investment Activity                       $4,500,000.00

Ending Balance (December 31, 2023):             $40,700,000.00

COMMITMENT INFORMATION

Total Commitment:                                $50,000,000.00
Drawn Commitment:                                $35,000,000.00
Unfunded Commitment:                             $15,000,000.00
Percentage Called:                                      70.00%

Ownership Percentage:                                    5.00%

PERFORMANCE SUMMARY (Since Inception)

Total Contributions:                             $35,000,000.00
Total Distributions:                             $18,000,000.00
Current NAV:                                     $40,700,000.00
Total Value (Distributions + NAV):               $58,700,000.00

Multiple on Invested Capital (MOIC):                     1.68x
Internal Rate of Return (IRR):                          18.5%

This statement is provided for informational purposes only.
"""

# Actual test document content from data/test_documents/sample_quarterly_report.txt
SAMPLE_QUARTERLY_REPORT_PDF = """
QUARTERLY REPORT

Astorg VII
Quarterly Report to Limited Partners
Quarter Ended: December 31, 2023

Dear Limited Partner,

We are pleased to provide you with the quarterly report for Astorg VII.

FUND OVERVIEW

Fund Size: €2,000,000,000
Vintage Year: 2021
Investment Period: Active
Geographic Focus: Europe

CAPITAL ACTIVITY

                                    Quarter         Year-to-Date
Capital Called                      €150M           €600M
Distributions                       €100M           €350M
Net Cash Flow                       €(50M)          €(250M)

PORTFOLIO SUMMARY

Total Investments: 12
New Investments This Quarter: 1
Realizations This Quarter: 0

KEY METRICS (as of December 31, 2023)

Net Asset Value (NAV):              €1,850,000,000
Total Contributions:                €1,200,000,000
Total Distributions:                €350,000,000
Residual Value:                     €1,850,000,000

PERFORMANCE METRICS

                    Gross           Net
IRR                 22.5%          18.5%
TVPI                1.78x          1.68x
DPI                 0.29x          0.29x
RVPI                1.54x          1.39x

TOP PORTFOLIO COMPANIES

1. Company A - Healthcare - €250M invested - 2.1x current multiple
2. Company B - Technology - €200M invested - 1.8x current multiple
3. Company C - Consumer - €180M invested - 1.5x current multiple
4. Company D - Industrial - €150M invested - 1.3x current multiple
5. Company E - Services - €120M invested - 1.9x current multiple

INVESTOR SPECIFIC INFORMATION

Investor: BrainWeb Investment GmbH
Commitment: €50,000,000
Ownership: 2.5%

Your Capital Account:
Beginning NAV (Oct 1):              €35,000,000
Contributions:                      €3,750,000
Distributions:                      €2,500,000
Net Change in Value:                €1,312,500
Ending NAV (Dec 31):                €37,562,500

Unfunded Commitment:                €15,000,000

We remain focused on creating value across our portfolio.

Sincerely,
Astorg Partners
"""

# Actual test document content from data/test_documents/sample_capital_call.txt
SAMPLE_CAPITAL_CALL_DOCUMENT = """CAPITAL CALL NOTICE

Date: March 15, 2024
Call Number: 13

To: BrainWeb Investment GmbH
    Attn: Finance Department

Re: Astorg VII - Capital Call Notice #13

Dear Limited Partner,

Pursuant to Section 6.1 of the Limited Partnership Agreement, we hereby notify you of the following capital call:

CAPITAL CALL DETAILS

Fund: Astorg VII
Capital Call Number: 13
Call Date: March 15, 2024
Due Date: April 5, 2024

YOUR CAPITAL CALL

Your Total Commitment:               $50,000,000.00
Your Ownership Percentage:                   5.00%

Previously Called:                   $35,000,000.00 (70.00%)
This Call:                           $3,000,000.00 (6.00%)
Total Called After This Call:        $38,000,000.00 (76.00%)
Remaining Uncalled:                  $12,000,000.00 (24.00%)

PURPOSE OF CAPITAL CALL

Investment in Portfolio Company:      $2,500,000.00
  - New platform acquisition in healthcare sector
  
Management Fees:                        $300,000.00
  - Q1 2024 management fee (2% annually on committed capital)
  
Fund Expenses:                          $200,000.00
  - Legal fees for new acquisition
  - Due diligence expenses
  - Fund administration

Total This Call:                      $3,000,000.00

PAYMENT INSTRUCTIONS

Please wire your capital contribution of $3,000,000.00 by April 5, 2024 to:

Bank: JPMorgan Chase Bank, N.A.
ABA/Routing: 021000021
Account Name: Astorg VII
Account Number: 123456789
Reference: Astorg VII - Call 13 - BWI

IMPORTANT NOTES

- Payment is due within 20 business days of this notice
- Late payments subject to interest at 10% per annum
- Please reference your investor ID (BWI-001) on all wire transfers

For questions, please contact:
Investor Relations
Email: ir@astorg.com
Phone: +33 1 2345 6789

Sincerely,

Astorg Partners
General Partner
"""

# Sample extraction results for testing - based on actual test documents
SAMPLE_EXTRACTION_RESULTS = {
    "capital_account": {
        "fund_name": "Astorg VII",
        "fund_manager": "Astorg Partners",
        "investor_name": "BrainWeb Investment GmbH",
        "investor_id": "BWI-001",
        "period_label": "Q4 2023",
        "as_of_date": "2023-12-31",
        "beginning_balance": 35000000.0,
        "ending_balance": 40700000.0,
        "contributions_period": 5000000.0,
        "distributions_period": 4000000.0,
        "management_fees_period": 250000.0,
        "partnership_expenses_period": 50000.0,
        "realized_gain_loss_period": 1500000.0,
        "unrealized_gain_loss_period": 3000000.0,
        "total_commitment": 50000000.0,
        "drawn_commitment": 35000000.0,
        "unfunded_commitment": 15000000.0,
        "ownership_percentage": 5.0,
        "total_contributions_itd": 35000000.0,
        "total_distributions_itd": 18000000.0,
        "current_nav": 40700000.0,
        "total_value": 58700000.0,
        "moic": 1.68,
        "irr": 18.5
    },
    "quarterly_report": {
        "fund_name": "Astorg VII",
        "period_label": "Q4 2023",
        "report_date": "2023-12-31",
        "fund_size": 2000000000.0,
        "vintage_year": 2021,
        "geographic_focus": "Europe",
        "fund_nav": 1850000000.0,
        "total_contributions": 1200000000.0,
        "total_distributions": 350000000.0,
        "residual_value": 1850000000.0,
        "gross_irr": 22.5,
        "net_irr": 18.5,
        "gross_tvpi": 1.78,
        "net_tvpi": 1.68,
        "dpi": 0.29,
        "rvpi": 1.39,
        "investor_commitment": 50000000.0,
        "investor_ownership": 2.5,
        "investor_beginning_nav": 35000000.0,
        "investor_contributions": 3750000.0,
        "investor_distributions": 2500000.0,
        "investor_ending_nav": 37562500.0,
        "investor_unfunded": 15000000.0
    },
    "capital_call": {
        "fund_name": "Astorg VII",
        "call_number": 13,
        "call_date": "2024-03-15",
        "due_date": "2024-04-05",
        "investor_name": "BrainWeb Investment GmbH",
        "investor_id": "BWI-001",
        "total_commitment": 50000000.0,
        "ownership_percentage": 5.0,
        "previously_called": 35000000.0,
        "this_call": 3000000.0,
        "total_called_after": 38000000.0,
        "remaining_uncalled": 12000000.0,
        "investment_amount": 2500000.0,
        "management_fees": 300000.0,
        "fund_expenses": 200000.0
    }
}

# Sample API responses
SAMPLE_API_RESPONSES = {
    "health_check": {
        "status": "healthy",
        "services": {
            "database": "connected",
            "vector_store": "connected",
            "file_watcher": "stopped"
        },
        "vector_stats": {
            "total_chunks": 150,
            "status": "connected"
        }
    },
    "investors": [
        {
            "id": "brainweb-001",
            "name": "BrainWeb Investment GmbH",
            "code": "brainweb",
            "description": "BrainWeb Investment GmbH - Private Equity and Venture Capital",
            "document_count": 25,
            "status": "active"
        },
        {
            "id": "pecunalta-001",
            "name": "pecunalta GmbH",
            "code": "pecunalta",
            "description": "pecunalta GmbH - Investment Management",
            "document_count": 18,
            "status": "active"
        }
    ],
    "documents": [
        {
            "id": "doc-001",
            "filename": "Q2_2023_Capital_Account.pdf",
            "document_type": "capital_account_statement",
            "confidence_score": 0.95,
            "summary": "Quarterly capital account statement for Q2 2023",
            "processing_status": "completed",
            "created_at": "2023-07-15T10:30:00Z",
            "investor_name": "BrainWeb Investment GmbH",
            "fund_name": "BrainWeb Growth Fund II"
        }
    ]
}