from app.ai.agents.base import AgentDefinition

AGENT = AgentDefinition(
    key="executive",
    display_name="Executive Assistant",
    role="CEO / Executive",
    description="Executive overview, summaries and coordination.",
    allowed_tools=[
        "slack_post_message",
        "search_crm",
        "list_tasks",
        "create_meeting",
        "summarize_meeting",
        "transcribe_meeting_audio",
        "search_knowledge",
        "get_document",
        "send_email",
        "approve_quotation",
        "reject_quotation",
        "generate_revenue_report",
        "generate_expense_report",
        "generate_sales_pipeline_report",
        "generate_productivity_report",
        "generate_forecast_report",
        "generate_customer_cohort_report",
    ],
    system_prompt=(
        "You support the executive team with overviews, meeting coordination "
        "and quick research. Prefer real numbers from the workspace."
    ),
    role_synonyms=("executive", "ceo", "assistant", "coo"),
)