from app.ai.agents.base import AgentDefinition

AGENT = AgentDefinition(
    key="accountant",
    display_name="AI Accountant",
    role="Accountant",
    description="Prepares invoices, reconciles payments and keeps books tidy.",
    allowed_tools=["create_invoice", "get_invoice", "list_invoices", "list_expenses", "create_expense", "create_quotation", "list_quotations", "generate_quotation_pdf_tool", "generate_invoice_pdf_tool", "mark_invoice_paid", "generate_invoice_payment_link", "send_quotation_email", "approve_quotation", "reject_quotation", "generate_revenue_report", "generate_expense_report", "generate_sales_pipeline_report", "generate_productivity_report", "generate_forecast_report", "generate_customer_cohort_report", "xero_create_invoice", "xero_list_invoices", "onedrive_upload_file", "onedrive_append_excel"],
    system_prompt=(
        "You are the company accountant. Prepare and verify invoices, track "
        "payments and flag discrepancies. Lead with the numbers."
    ),
    role_synonyms=("account", "bookkeeper", "finance"),
)