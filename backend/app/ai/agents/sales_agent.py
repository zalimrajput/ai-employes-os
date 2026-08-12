from app.ai.agents.base import AgentDefinition

AGENT = AgentDefinition(
    key="sales",
    display_name="Sales Agent",
    role="Sales Manager",
    description="Finds leads, supports the pipeline and drafts sales outreach.",
    allowed_tools=["search_crm", "get_customer", "list_leads", "list_deals", "create_activity", "summarize_customer", "list_quotations", "create_reminder", "list_reminders", "create_meeting", "list_meetings", "summarize_meeting", "transcribe_meeting_audio", "send_email", "send_quotation_email", "submit_quotation_for_approval", "classify_email_thread", "summarize_email_thread", "zoho_create_lead", "zoho_list_leads", "drive_upload_file", "sheets_append_row", "slack_post_message"],
    system_prompt=(
        "You help with pipeline management, lead follow-ups and outreach. "
        "When asked about prospects, search the CRM first and answer from real "
        "data. Keep answers sales-focused and actionable."
    ),
    role_synonyms=("sales", "business development", "bdm", "account executive"),
)