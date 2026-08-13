import { supabase } from "@/lib/supabase/client";
import type {
  AIConversation,
  AIMessage,
  Activity,
  Budget,
  Customer,
  CustomerCreate,
  DepartmentCreate,
  EmailThread,
  Employee,
  Expense,
  ImagePart,
  Invoice,
  InvoiceCreate,
  JobCandidate,
  Lead,
  LeadCreate,
  LeaveRequest,
  LoginRequest,
  MarketingCampaign,
  Meeting,
  MeetingCreate,
  OrgDepartment,
  OrganizationCreate,
  OrganizationResponse,
  Plan,
  Quotation,
  QuotationCreate,
  Task,
  TokenResponse,
  UserCreate,
  UserResponse,
  WhatsAppMessage,
} from "@/lib/api/types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/**
 * Resolve the Supabase session access token from the browser.
 * Returns null when the user is signed out.
 */
async function getAccessToken(): Promise<string | null> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

/**
 * Base fetch against the FastAPI backend.
 * - `auth: true` (default) attaches `Authorization: Bearer <supabase token>`.
 * - Returns the parsed JSON body on 2xx.
 * - Throws an Error with a readable message on non-2xx.
 */
async function apiFetch<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    body?: unknown;
    auth?: boolean;
  } = {}
): Promise<T> {
  const { method = "GET", body, auth = true } = options;

  const headers: Record<string, string> = {};

  if (auth) {
    const token = await getAccessToken();
    if (!token) {
      throw new Error("Not authenticated — please sign in first.");
    }
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error(`Could not reach the backend at ${BACKEND_URL}. Is it running?`);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(`${res.status}: ${detail}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export const api = {
  /** Public — exchanges email/password for Supabase tokens via the backend. */
  login: (body: LoginRequest) =>
    apiFetch<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body,
      auth: false,
    }),

  /** Protected — creates a workspace; the caller becomes its creator/member. */
  createOrganization: (body: OrganizationCreate) =>
    apiFetch<OrganizationResponse>("/api/v1/organizations/", {
      method: "POST",
      body,
    }),

  /** Protected — admin only: creates a Supabase Auth user + assigns an org. */
  createUser: (body: UserCreate) =>
    apiFetch<UserResponse>("/api/v1/users/", { method: "POST", body }),

  /** Protected — org admin: deletes a user from their organization. */
  deleteUser: (userId: string) =>
    apiFetch<{ id: string; deleted: boolean }>(`/api/v1/users/${userId}`, {
      method: "DELETE",
    }),

  /** Protected — super admin: toggles a module for an organization. */
  updateOrgModuleAdmin: (orgId: string, moduleKey: string, enabled: boolean) =>
    apiFetch<Record<string, unknown>>(
      `/api/v1/modules/org/${orgId}/${moduleKey}`,
      { method: "PATCH", body: { enabled_by_super_admin: enabled } }
    ),

  /** Protected — org admin: toggles a module for their own workspace. */
  updateMyModule: (moduleKey: string, enabled: boolean) =>
    apiFetch<Record<string, unknown>>(`/api/v1/modules/me/${moduleKey}`, {
      method: "PATCH",
      body: { enabled_by_org_admin: enabled },
    }),

  /** Protected — lists departments of the caller's organization. */
  fetchDepartments: () => apiFetch<OrgDepartment[]>("/api/v1/departments/"),

  /** Protected — org admin: creates a department. */
  createDepartment: (body: DepartmentCreate) =>
    apiFetch<OrgDepartment>("/api/v1/departments/", {
      method: "POST",
      body,
    }),

  /** Protected — org admin: deletes a department. */
  deleteDepartment: (departmentId: string) =>
    apiFetch<{ id: string; deleted: boolean }>(
      `/api/v1/departments/${departmentId}`,
      { method: "DELETE" }
    ),

  // ── CRM (customers & leads) ──────────────────────────────
  fetchCustomers: () => apiFetch<Customer[]>("/api/v1/customers/"),
  createCustomer: (body: CustomerCreate) =>
    apiFetch<Customer>("/api/v1/customers/", { method: "POST", body }),
  fetchLeads: () => apiFetch<Lead[]>("/api/v1/leads/"),
  createLead: (body: LeadCreate) =>
    apiFetch<Lead>("/api/v1/leads/", { method: "POST", body }),

  // ── Sales (quotations) ───────────────────────────────────
  fetchQuotations: () => apiFetch<Quotation[]>("/api/v1/quotations/"),
  createQuotation: (body: QuotationCreate) =>
    apiFetch<Quotation>("/api/v1/quotations/", { method: "POST", body }),

  // ── Finance (invoices) ───────────────────────────────────
  fetchInvoices: () => apiFetch<Invoice[]>("/api/v1/invoices/"),
  createInvoice: (body: InvoiceCreate) =>
    apiFetch<Invoice>("/api/v1/invoices/", { method: "POST", body }),

  // ── Meetings / Calendar ──────────────────────────────────
  fetchMeetings: () => apiFetch<Meeting[]>("/api/v1/meetings/"),
  createMeeting: (body: MeetingCreate) =>
    apiFetch<Meeting>("/api/v1/meetings/", { method: "POST", body }),

  // ── CRM activities ───────────────────────────────────────
  fetchActivities: () => apiFetch<Activity[]>("/api/v1/activities/"),

  // ── HR ───────────────────────────────────────────────────
  fetchEmployees: () => apiFetch<Employee[]>("/api/v1/employees/"),
  fetchLeaveRequests: () => apiFetch<LeaveRequest[]>("/api/v1/leave-requests/"),
  fetchCandidates: () => apiFetch<JobCandidate[]>("/api/v1/candidates/"),

  // ── Support (email + WhatsApp) ───────────────────────────
  fetchEmailThreads: () => apiFetch<EmailThread[]>("/api/v1/email-threads/"),
  fetchWhatsappMessages: () => apiFetch<WhatsAppMessage[]>("/api/v1/whatsapp-messages/"),

  // ── Marketing ────────────────────────────────────────────
  fetchCampaigns: () => apiFetch<MarketingCampaign[]>("/api/v1/campaigns/"),

  // ── Finance (budgets & expenses) ─────────────────────────
  fetchBudgets: () => apiFetch<Budget[]>("/api/v1/budgets/"),
  fetchExpenses: () => apiFetch<Expense[]>("/api/v1/expenses/"),

  // ── Billing plans (public catalog) ───────────────────────
  fetchPlans: () => apiFetch<Plan[]>("/api/v1/billing/plans"),

  // ── Tasks ────────────────────────────────────────────────
  fetchTasks: () => apiFetch<Task[]>("/api/v1/tasks/"),
  createTask: (body: Partial<Task>) =>
    apiFetch<Task>("/api/v1/tasks/", { method: "POST", body }),
  updateTask: (id: string, body: Partial<Pick<Task, "status" | "priority" | "title" | "description" | "due_date">>) =>
    apiFetch<Task>(`/api/v1/tasks/${id}`, { method: "PATCH", body }),

  // ── Analytics summary (live counts) ──────────────────────
  fetchAnalyticsSummary: () =>
    apiFetch<Record<string, number>>("/api/v1/analytics/summary"),

  // ── AI Chat (real agent engine) ──────────────────────────
  /** Protected — lists the caller's org AI conversations. */
  fetchAIConversations: () => apiFetch<AIConversation[]>("/api/v1/ai-chat/conversations"),

  /** Protected — creates an AI conversation in the caller's org. */
  createAIConversation: (body: { ai_employee_id?: string; title?: string }) =>
    apiFetch<AIConversation>("/api/v1/ai-chat/conversations", { method: "POST", body }),

  /** Protected — lists the messages of one org-scoped conversation. */
  fetchAIMessages: (conversationId: string) =>
    apiFetch<AIMessage[]>(`/api/v1/ai-chat/conversations/${conversationId}/messages`),

  /** Protected — sends a message (optionally with image attachments) and runs the AI agent. */
  sendAIMessage: (body: {
    conversation_id: string;
    message?: string;
    images?: ImagePart[];
  }) => apiFetch<AIMessage>("/api/v1/ai-chat/messages", { method: "POST", body }),

  // ── Integrations (OAuth connect flow) ─────────────────────
  /** Protected — per-provider configured/connected state (no tokens). */
  fetchIntegrationStatus: () =>
    apiFetch<
      {
        provider: string;
        configured: boolean;
        connected: boolean;
        phone_number_id?: string | null;
      }[]
    >("/api/v1/integrations/status"),

  /**
   * Protected — returns the provider authorization URL. Callers should
   * `window.location.assign(url)` so the user lands on Google/Microsoft/Slack.
   */
  connectIntegration: (provider: string) =>
    apiFetch<{ authorize_url: string }>(
      `/api/v1/integrations/oauth/connect/${provider}`
    ),

  /**
   * Protected — live connectivity check for env-key providers
   * (whatsapp / stripe / r2). Read-only; returns the exact failure reason.
   */
  checkIntegration: (provider: string) =>
    apiFetch<{
      provider: string;
      configured: boolean;
      connected: boolean;
      detail?: string;
    }>(`/api/v1/integrations/check/${provider}`),

  /**
   * Protected — stores the ORGANIZATION'S OWN WhatsApp Cloud API credentials
   * (token + phone number ID). Verified live against Meta before saving.
   */
  saveWhatsappCredentials: (body: {
    api_token: string;
    phone_number_id: string;
  }) =>
    apiFetch<{
      provider: string;
      configured: boolean;
      connected: boolean;
      detail?: string;
    }>("/api/v1/integrations/whatsapp/credentials", {
      method: "POST",
      body,
    }),
};
