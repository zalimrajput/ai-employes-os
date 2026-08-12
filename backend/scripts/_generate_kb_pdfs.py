"""Generate RAG-ready knowledge base PDFs from the project documentation.

Each PDF is written with reportlab as text (no images), so pypdf can extract
clean text and the document ingestion pipeline (chunk -> embed -> pgvector)
indexes it for the search_knowledge RAG tool.

Run:  python scripts/_generate_kb_pdfs.py
Output: backend/knowledge/*.pdf
"""
import os
import re
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # noqa: E402


def _read(name: str) -> str:
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _clean_md(text: str) -> str:
    """Strip markdown formatting for PDF paragraphs."""
    lines = []
    for line in (text or "").splitlines():
        line = re.sub(r"```", "", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)  # images
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)  # links
        line = line.rstrip()
        if line.strip():
            lines.append(line.rstrip())
    return "\n".join(lines)


def build_document(title: str, md_source: str, subtitle: str = "") -> list:
    """Turn markdown into reportlab flowables (title + sections)."""
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, spaceAfter=8)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4)
    h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11, spaceBefore=6, spaceAfter=2)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5, leading=13, spaceAfter=4)

    story = [Paragraph(title, h1)]
    if subtitle:
        story.append(Paragraph(subtitle, body))
    story.append(Spacer(1, 6))

    md = md_source or ""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level, heading = len(m.group(1)), m.group(2).strip()
            story.append(Paragraph(heading, h2 if level <= 2 else h3))
            i += 1
            # Collect following lines until the next heading.
            while i < len(lines) and not re.match(r"^\s*#{1,4}\s+", lines[i]):
                content = lines[i].strip()
                if content:
                    for para in _split_paragraphs(content):
                        story.append(Paragraph(para, body))
                i += 1
            continue
        if line and not line.startswith(("|", "---")):
            for para in _split_paragraphs(line):
                story.append(Paragraph(para, body))
        i += 1
    return story


def _split_paragraphs(line: str) -> list[str]:
    """Break long lines into paragraphs; bullet lines stay as bullets."""
    if line.startswith(("- ", "• ", "* ")):
        return [line]
    out = []
    for part in re.split(r"\.\s+(?=[A-Z])", line):
        part = part.strip()
        if not part:
            continue
        # Only append a period to plain sentences, never to URLs, code,
        # list tails, or already-punctuated lines.
        if part.endswith((")", ":", ".", ",", ";")) or "/" in part or "http" in part:
            out.append(part)
        else:
            out.append(part + ".")
    return out or [line]


def _make_pdf(path: str, title: str, flowables: list) -> None:
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )
    doc.build(flowables)
    print(f"  wrote {os.path.relpath(path, BACKEND)}")


def main() -> None:
    out_dir = os.path.join(BACKEND, "knowledge")
    os.makedirs(out_dir, exist_ok=True)

    # ── 1. Product overview ──────────────────────────────────────────────
    prd = _read("PRD.md")
    print("Generating knowledge PDFs from project docs...")

    overview_md = _clean_md(prd)
    _make_pdf(
        os.path.join(out_dir, "ai-employee-os-overview.pdf"),
        "AI Employee OS — Product Overview & Vision",
        build_document("AI Employee OS — Product Overview & Vision", overview_md),
    )

    # ── 2. AI employees & capabilities ───────────────────────────────────
    # Load the live agent catalog when the app env is available; otherwise
    # fall back to a static catalog so the script stays runnable anywhere.
    try:
        from app.ai.agents import ALL_AGENTS  # noqa: E402
    except Exception:
        ALL_AGENTS = []

    agent_lines = ["## AI Employee Catalog"]
    if not ALL_AGENTS:
        agent_lines = [
            "## AI Employee Catalog",
            "- AI Executive Assistant (executive): CEO briefings, reports, meetings, knowledge search.",
            "- AI Sales Assistant (sales): CRM search, leads, deals, quotations, quotation email, reminders, meetings.",
            "- AI Accountant (accountant): invoices, expenses, quotations, approvals, reports.",
            "- AI Finance Assistant (finance): invoices and expenses.",
            "- AI HR Assistant (hr): employees, leave, tasks, productivity reports.",
            "- AI Recruiter (recruiter): candidates, meetings, tasks, transcripts.",
            "- AI Customer Support Agent (support): CRM search, customers, tasks, email threads.",
            "- AI Marketing Assistant (marketing): campaigns, email drafts, tasks.",
            "- AI Content Writer (content_writer): email drafts, campaigns, knowledge search.",
            "- AI Legal Assistant (legal): documents, knowledge, contract analysis.",
            "- AI Inventory Manager (inventory): inventory, suppliers, tasks.",
            "- AI Procurement Assistant (procurement): purchase orders, suppliers, tasks.",
            "- AI Manager (master): orchestrator that delegates to all specialist agents.",
        ]
    for a in ALL_AGENTS:
        tools = ", ".join(sorted(a.allowed_tools or [])) or "—"
        agent_lines.append(f"- **{a.display_name}** (key: {a.key}, role: {a.role}): {a.description} Tools: {tools}.")
    catalog_md = "\n".join(agent_lines)
    _make_pdf(
        os.path.join(out_dir, "ai-employees-and-tools.pdf"),
        "AI Employees & Tools Catalog",
        build_document("AI Employees & Tools Catalog", catalog_md),
    )

    # ── 3. Architecture & API ────────────────────────────────────────────
    arch = _read("ARCHITECTURE.md")
    api = _read("API_SPEC.md")
    _make_pdf(
        os.path.join(out_dir, "architecture-and-api.pdf"),
        "Architecture & API Reference",
        build_document("Architecture & API Reference", f"{arch}\n\n{api}"),
    )

    # ── 4. Integrations guide ────────────────────────────────────────────
    integrations_md = _clean_md(
        "## Supported integrations\n"
        "- Gmail: OAuth connect, send + list email via Gmail API, auto token refresh.\n"
        "- Google Calendar: OAuth connect, create + list events on the primary calendar.\n"
        "- Outlook (Microsoft Graph): OAuth connect, send email, list messages, attachments.\n"
        "- Microsoft 365 (Microsoft Graph): OAuth connect, mail, calendar events, To-Do tasks.\n"
        "- Slack: Web API chat.postMessage with workspace token.\n"
        "- WhatsApp Business (Meta Cloud API): send text, media download, webhook.\n"
        "- Stripe: invoice payment links, Checkout Sessions, QR codes, webhook.\n"
        "- OpenAI Whisper: meeting audio transcription.\n"
        "- OCR (Tesseract): scanned document text extraction.\n"
        "- Accounting: API-key client pushing invoices and expenses.\n"
        "- Storage: Supabase-backed per-org file storage with quotas.\n\n"
        "## Configuration\n"
        "OAuth providers need CLIENT_ID/CLIENT_SECRET/REDIRECT_URI settings in .env. "
        "WhatsApp needs WHATSAPP_API_TOKEN and WHATSAPP_PHONE_ID. Stripe needs STRIPE_SECRET_KEY. "
        "All integration tokens are stored encrypted in the integrations table.\n\n"
        "## Connect flow\n"
        "Settings page -> Connect -> GET /api/v1/integrations/oauth/connect/{provider} "
        "returns an authorize URL -> OAuth callback exchanges the code, encrypts and stores tokens."
    )
    _make_pdf(
        os.path.join(out_dir, "integrations-guide.pdf"),
        "Integrations Guide",
        build_document("Integrations Guide", integrations_md),
    )

    # ── 5. Pricing & plans ───────────────────────────────────────────────
    pricing_md = _clean_md(
        "## Pricing Plans\n"
        "- Basic ($19/month): 1 user, 500 AI requests/month, email drafting, basic WhatsApp replies, "
        "100 invoices, 100 quotations, basic CRM, basic reports, 1 GB storage, email support.\n"
        "- Pro ($49/month): everything in Basic plus 5 users, 10,000 AI requests, advanced CRM, "
        "WhatsApp automation, meeting summaries, task management, calendar integration, workflow "
        "automation, 20 GB storage, priority support.\n"
        "- Business ($149/month): everything in Pro plus unlimited users and AI requests (fair use), "
        "multiple AI employees, department permissions, API access, ERP integrations, custom workflows, "
        "advanced analytics, audit logs, SSO, 200 GB storage, dedicated manager, 24/7 support."
    )
    _make_pdf(
        os.path.join(out_dir, "pricing-and-plans.pdf"),
        "Pricing & Plans",
        build_document("Pricing & Plans", pricing_md),
    )

    # ── 6. Usage examples ────────────────────────────────────────────────
    examples_md = _clean_md(
        "## Example workflows\n"
        "- Send a quotation: user says 'send quotation to John for 25 laptops' -> Sales Agent finds the "
        "customer, lists approved quotations, sends the quotation email, records an activity.\n"
        "- Invoice paid automation: customer pays via Stripe payment link -> workflow generates a receipt, "
        "updates the CRM, notifies the sales team, sends a thank-you email, and schedules a follow-up.\n"
        "- Meeting intelligence: transcribe meeting audio (Whisper), summarize it, extract action items, "
        "and create tasks.\n"
        "- Department chat isolation: sales users chat with the AI Sales Assistant, finance with the AI "
        "Finance Assistant, and conversations are scoped per department with admin visibility.\n"
        "- Document Q&A: upload PDFs into the knowledge base, the search_knowledge tool retrieves relevant "
        "chunks via pgvector and the agent answers with the company knowledge."
    )
    _make_pdf(
        os.path.join(out_dir, "usage-examples.pdf"),
        "Usage Examples & Workflows",
        build_document("Usage Examples & Workflows", examples_md),
    )

    print(f"\nDone. {len(os.listdir(out_dir))} PDFs in backend/knowledge/")


if __name__ == "__main__":
    main()
