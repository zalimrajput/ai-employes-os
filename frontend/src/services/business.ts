import { api } from "@/lib/api/client";
import { formatCurrency, initials } from "@/lib/utils";
import type {
  Activity,
  Budget,
  Customer,
  CustomerCreate,
  EmailThread,
  Employee,
  Expense,
  Invoice,
  InvoiceCreate,
  JobCandidate,
  Lead,
  LeadCreate,
  LeaveRequest,
  MarketingCampaign,
  Meeting,
  MeetingCreate,
  Plan,
  Quotation,
  QuotationCreate,
  WhatsAppMessage,
} from "@/lib/api/types";

/**
 * Business-data access helpers backed by the live FastAPI endpoints
 * (`/api/v1/customers`, `/quotations`, `/invoices`, `/meetings`, ...).
 *
 * All data comes from the backend/DB — there is no demo fallback. When a
 * workspace is empty the fetchers return an empty list and pages show empty
 * states.
 */

export type DataResult<T> =
  | { source: "db"; items: T[] }
  | { source: "error"; error: string };

async function list<T>(fetcher: () => Promise<T[]>): Promise<DataResult<T>> {
  try {
    const items = await fetcher();
    return { source: "db", items };
  } catch (err) {
    return { source: "error", error: (err as Error).message };
  }
}

// ── Customers ──────────────────────────────────────────────
export function fetchCustomers(): Promise<DataResult<Customer>> {
  return list(() => api.fetchCustomers());
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
  return list(() => api.fetchLeads());
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
  return list(() => api.fetchQuotations());
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
  return list(() => api.fetchInvoices());
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
  return list(() => api.fetchMeetings());
}

export async function createMeeting(input: MeetingCreate): Promise<{ error: string | null }> {
  try {
    await api.createMeeting(input);
    return { error: null };
  } catch (err) {
    return { error: (err as Error).message };
  }
}

// ── CRM activities ─────────────────────────────────────────
export function fetchActivities(): Promise<DataResult<Activity>> {
  return list(() => api.fetchActivities());
}

// ── HR ─────────────────────────────────────────────────────
export function fetchEmployees(): Promise<DataResult<Employee>> {
  return list(() => api.fetchEmployees());
}

export function fetchLeaveRequests(): Promise<DataResult<LeaveRequest>> {
  return list(() => api.fetchLeaveRequests());
}

export function fetchCandidates(): Promise<DataResult<JobCandidate>> {
  return list(() => api.fetchCandidates());
}

// ── Support (email + WhatsApp) ─────────────────────────────
export function fetchEmailThreads(): Promise<DataResult<EmailThread>> {
  return list(() => api.fetchEmailThreads());
}

export function fetchWhatsappMessages(): Promise<DataResult<WhatsAppMessage>> {
  return list(() => api.fetchWhatsappMessages());
}

// ── Marketing ──────────────────────────────────────────────
export function fetchCampaigns(): Promise<DataResult<MarketingCampaign>> {
  return list(() => api.fetchCampaigns());
}

// ── Finance (budgets & expenses) ───────────────────────────
export function fetchBudgets(): Promise<DataResult<Budget>> {
  return list(() => api.fetchBudgets());
}

export function fetchExpenses(): Promise<DataResult<Expense>> {
  return list(() => api.fetchExpenses());
}

// ── Billing plans (platform catalog) ───────────────────────
export function fetchPlans(): Promise<DataResult<Plan>> {
  return list(() => api.fetchPlans());
}

// ── Formatting helpers (reuse utils implementations, keep null-safety) ──
export { initials };

/** Null-safe currency formatter (accepts the nullable amount columns). */
export const currency = (n: number | null | undefined): string =>
  formatCurrency(n ?? 0);
