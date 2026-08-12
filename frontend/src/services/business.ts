import { api } from "@/lib/api/client";
import { formatCurrency, initials } from "@/lib/utils";
import type {
  Customer,
  CustomerCreate,
  Invoice,
  InvoiceCreate,
  Lead,
  LeadCreate,
  Meeting,
  MeetingCreate,
  Quotation,
  QuotationCreate,
} from "@/lib/api/types";

/**
 * Business-data access helpers backed by the live FastAPI endpoints
 * (`/api/v1/customers`, `/quotations`, `/invoices`, `/meetings`, ...).
 *
 * Pattern mirrors `services/data.ts`: when a workspace is empty we return
 * curated demo rows so the UI stays alive, flagged via `source: "demo"`.
 * Real rows created through the backend automatically take over.
 */

export type DataResult<T> =
  | { source: "db" | "demo"; items: T[] }
  | { source: "error"; error: string };

/**
 * Demo mode is opt-in via NEXT_PUBLIC_ENABLE_DEMO=true (dev/preview only).
 * In production (unset/false) empty workspaces return an empty list instead of
 * curated fake rows, so real customers never see demo data.
 */
export function isDemoEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ENABLE_DEMO === "true";
}

function withDemo<T>(
  fetcher: () => Promise<T[]>,
  demo: T[]
): Promise<DataResult<T>> {
  return fetcher()
    .then((items) =>
      items.length > 0
        ? { source: "db" as const, items }
        : isDemoEnabled()
          ? { source: "demo" as const, items: demo }
          : { source: "db" as const, items: [] }
    )
    .catch((err) => ({ source: "error" as const, error: (err as Error).message }));
}

// ── Customers ──────────────────────────────────────────────
export function fetchCustomers(): Promise<DataResult<Customer>> {
  return withDemo(() => api.fetchCustomers(), DEMO_CUSTOMERS);
}

export async function createCustomer(input: CustomerCreate): Promise<{ error: string | null }> {
  try {
    await api.createCustomer(input);
    return { error: null };
  } catch (err) {
    return { error: (err as Error).message };
  }
}

// ── Leads ──────────────────────────────────────────────────
export function fetchLeads(): Promise<DataResult<Lead>> {
  return withDemo(() => api.fetchLeads(), DEMO_LEADS);
}

export async function createLead(input: LeadCreate): Promise<{ error: string | null }> {
  try {
    await api.createLead(input);
    return { error: null };
  } catch (err) {
    return { error: (err as Error).message };
  }
}

// ── Quotations ─────────────────────────────────────────────
export function fetchQuotations(): Promise<DataResult<Quotation>> {
  return withDemo(() => api.fetchQuotations(), DEMO_QUOTATIONS);
}

export async function createQuotation(input: QuotationCreate): Promise<{ error: string | null }> {
  try {
    await api.createQuotation(input);
    return { error: null };
  } catch (err) {
    return { error: (err as Error).message };
  }
}

// ── Invoices ───────────────────────────────────────────────
export function fetchInvoices(): Promise<DataResult<Invoice>> {
  return withDemo(() => api.fetchInvoices(), DEMO_INVOICES);
}

export async function createInvoice(input: InvoiceCreate): Promise<{ error: string | null }> {
  try {
    await api.createInvoice(input);
    return { error: null };
  } catch (err) {
    return { error: (err as Error).message };
  }
}

// ── Meetings ───────────────────────────────────────────────
export function fetchMeetings(): Promise<DataResult<Meeting>> {
  return withDemo(() => api.fetchMeetings(), DEMO_MEETINGS);
}

export async function createMeeting(input: MeetingCreate): Promise<{ error: string | null }> {
  try {
    await api.createMeeting(input);
    return { error: null };
  } catch (err) {
    return { error: (err as Error).message };
  }
}

// ── Formatting helpers (reuse utils implementations, keep null-safety) ──
export { initials };

/** Null-safe currency formatter (accepts the nullable amount columns). */
export const currency = (n: number | null | undefined): string =>
  formatCurrency(n ?? 0);

// ── Demo data (fresh workspaces) ───────────────────────────
export const DEMO_CUSTOMERS: Customer[] = [
  { id: "demo-cust-1", organization_id: "", name: "Acme Corp", company: "Enterprise", email: "john@acme.io", status: "active" },
  { id: "demo-cust-2", organization_id: "", name: "GlobalTech", company: "Mid-market", email: "sara@globaltech.dev", status: "active" },
  { id: "demo-cust-3", organization_id: "", name: "Nova Retail", company: "SMB", email: "mike@novaretail.com", status: "active" },
  { id: "demo-cust-4", organization_id: "", name: "BrightLaw LLP", company: "Mid-market", email: "emma@brightlaw.com", status: "active" },
];

export const DEMO_LEADS: Lead[] = [
  { id: "demo-lead-1", organization_id: "", name: "Acme Corp", email: "john@acme.io", company: "Acme Corp", value: "$48,500", status: "Proposal" },
  { id: "demo-lead-2", organization_id: "", name: "GlobalTech", email: "sara@globaltech.dev", company: "GlobalTech", value: "$92,000", status: "Negotiation" },
  { id: "demo-lead-3", organization_id: "", name: "Nova Retail", email: "mike@novaretail.com", company: "Nova Retail", value: "$24,000", status: "Qualified" },
  { id: "demo-lead-4", organization_id: "", name: "BrightLaw LLP", email: "emma@brightlaw.com", company: "BrightLaw LLP", value: "$61,200", status: "Lead" },
];

export const DEMO_QUOTATIONS: Quotation[] = [
  { id: "demo-q1", organization_id: "", quotation_number: "Q-1042", customer_id: "demo-cust-1", status: "sent", total: 12400 },
  { id: "demo-q2", organization_id: "", quotation_number: "Q-1043", customer_id: "demo-cust-2", status: "approved", total: 8900 },
  { id: "demo-q3", organization_id: "", quotation_number: "Q-1044", customer_id: "demo-cust-3", status: "draft", total: 3200 },
  { id: "demo-q4", organization_id: "", quotation_number: "Q-1045", customer_id: "demo-cust-4", status: "sent", total: 5750 },
];

export const DEMO_INVOICES: Invoice[] = [
  { id: "demo-inv-1", organization_id: "", invoice_number: "INV-1042", customer_id: "demo-cust-1", amount: 12400, status: "paid", due_date: "2026-07-28" },
  { id: "demo-inv-2", organization_id: "", invoice_number: "INV-1043", customer_id: "demo-cust-2", amount: 8900, status: "pending", due_date: "2026-08-04" },
  { id: "demo-inv-3", organization_id: "", invoice_number: "INV-1044", customer_id: "demo-cust-3", amount: 3200, status: "overdue", due_date: "2026-07-21" },
  { id: "demo-inv-4", organization_id: "", invoice_number: "INV-1045", customer_id: "demo-cust-4", amount: 5750, status: "draft", due_date: "2026-08-10" },
];

export const DEMO_MEETINGS: Meeting[] = [
  { id: "demo-mtg-1", organization_id: "", title: "Team standup", start_time: "2026-08-01T09:00:00Z" },
  { id: "demo-mtg-2", organization_id: "", title: "Design review — landing page", start_time: "2026-08-01T11:00:00Z" },
  { id: "demo-mtg-3", organization_id: "", title: "1:1 with Alex Morgan", start_time: "2026-08-01T16:00:00Z" },
];
