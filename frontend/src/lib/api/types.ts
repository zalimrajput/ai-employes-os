// Domain types mirroring the backend Pydantic schemas and Supabase tables.

// ── Auth ──────────────────────────────────────────────────
export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string | null;
  token_type: string;
}

// ── Organizations ─────────────────────────────────────────
export interface OrganizationCreate {
  name: string;
  slug: string;
  industry?: string | null;
  country?: string | null;
}

export interface OrganizationResponse {
  id: string;
  name: string;
  slug: string;
  industry?: string | null;
  country?: string | null;
  timezone: string;
  logo_url?: string | null;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ── Users ─────────────────────────────────────────────────
export interface UserCreate {
  organization_id: string;
  full_name?: string | null;
  email: string;
  password: string;
  phone?: string | null;
  role_name?: string | null;
}

export interface UserResponse {
  id: string;
  organization_id: string;
  full_name?: string | null;
  email: string;
  avatar_url?: string | null;
  phone?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

// ── AI Employees ──────────────────────────────────────────
export interface AIEmployee {
  id: string;
  organization_id: string;
  name: string;
  role: string;
  description?: string | null;
  model?: string | null;
  system_prompt?: string | null;
  tools?: Record<string, unknown>;
  permissions?: Record<string, unknown>;
  active?: boolean;
  created_at?: string;
}

// ── Tasks ─────────────────────────────────────────────────
export type TaskStatus = "todo" | "in_progress" | "review" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface Task {
  id: string;
  organization_id?: string | null;
  assigned_to?: string | null;
  created_by?: string | null;
  title: string;
  description?: string | null;
  priority?: TaskPriority;
  status?: TaskStatus;
  due_date?: string | null;
  ai_created?: boolean;
  created_at?: string;
}

// ── Workflows ─────────────────────────────────────────────
export interface Workflow {
  id: string;
  organization_id?: string | null;
  name?: string | null;
  trigger?: unknown;
  actions?: unknown;
  active?: boolean;
  created_at?: string;
}

// ── AI Conversations & Messages ───────────────────────────
export interface AIConversation {
  id: string;
  organization_id?: string | null;
  user_id?: string | null;
  ai_employee_id?: string | null;
  title?: string | null;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AIMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  message: string;
  tool_calls?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string;
}

/** OpenAI-style image part sent with a chat message (data:image/...;base64,... URI). */
export interface ImagePart {
  type: "image_url";
  image_url: { url: string };
}

// ── Analytics / Usage ─────────────────────────────────────
export interface OrgStats {
  employees: number;
  tasks: number;
  workflows: number;
  conversations: number;
  messages: number;
  activeEmployees: number;
}

// ── Platform admin (super admin) ──────────────────────────
export interface OrgWithStats {
  id: string;
  name: string;
  slug: string;
  industry?: string | null;
  country?: string | null;
  plan: string;
  status: string;
  max_users?: number | null;
  storage_limit_gb?: number | null;
  created_at: string;
  users: number;
  modules: OrgModuleRow[];
}

export interface OrgModuleRow {
  id: string;
  organization_id: string;
  module_key: string;
  enabled_by_super_admin: boolean;
  enabled_by_org_admin: boolean;
}

export interface OrgMember {
  id: string;
  full_name?: string | null;
  email?: string | null;
  avatar_url?: string | null;
  status: string;
  created_at: string;
  roles: string[];
}

export interface OrgRole {
  id: string;
  name: string;
  description?: string | null;
  permissions?: Record<string, unknown> | null;
}

// ── CRM / Sales / Finance business records ─────────────────
export interface Customer {
  id: string;
  organization_id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  address?: string | null;
  notes?: string | null;
  ai_summary?: string | null;
  status?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface CustomerCreate {
  name: string;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  address?: string | null;
  notes?: string | null;
  status?: string | null;
}

export interface Lead {
  id: string;
  organization_id: string;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  /** Display value of the potential deal (e.g. "$48,500"). */
  value?: string | null;
  source?: string | null;
  status?: string | null;
  score?: number | null;
  assigned_to?: string | null;
  created_at?: string;
}

export interface LeadCreate {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  source?: string | null;
  status?: string | null;
  score?: number | null;
}

export interface Quotation {
  id: string;
  organization_id: string;
  customer_id?: string | null;
  quotation_number?: string | null;
  status?: string | null;
  subtotal?: number | null;
  tax?: number | null;
  discount?: number | null;
  total?: number | null;
  pdf_url?: string | null;
  created_at?: string;
}

export interface QuotationCreate {
  customer_id?: string | null;
  quotation_number?: string | null;
  status?: string | null;
  subtotal?: number | null;
  tax?: number | null;
  discount?: number | null;
  total?: number | null;
}

export interface Invoice {
  id: string;
  organization_id: string;
  customer_id?: string | null;
  invoice_number?: string | null;
  amount?: number | null;
  status?: string | null;
  due_date?: string | null;
  pdf_url?: string | null;
  recurrence_interval?: number | null;
  recurrence_period?: string | null;
  next_billing_date?: string | null;
  payment_link_url?: string | null;
  qr_code_url?: string | null;
  ai_summary?: string | null;
  created_at?: string;
}

export interface InvoiceCreate {
  customer_id?: string | null;
  invoice_number?: string | null;
  amount?: number | null;
  status?: string | null;
  due_date?: string | null;
}

export interface Meeting {
  id: string;
  organization_id: string;
  title?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  participants?: unknown;
  transcript?: string | null;
  summary?: string | null;
  action_items?: unknown;
  created_at?: string;
  updated_at?: string;
}

export interface MeetingCreate {
  title?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  participants?: unknown;
}

// ── HR ─────────────────────────────────────────────────────
export interface Employee {
  id: string;
  organization_id: string;
  user_id?: string | null;
  employee_code?: string | null;
  first_name: string;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  department_id?: string | null;
  position?: string | null;
  joining_date?: string | null;
  salary?: number | null;
  status?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string;
}

export interface LeaveRequest {
  id: string;
  organization_id?: string | null;
  employee_id?: string | null;
  leave_type?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  reason?: string | null;
  status?: string | null;
  approved_by?: string | null;
  created_at?: string;
}

export interface JobCandidate {
  id: string;
  organization_id?: string | null;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  resume_url?: string | null;
  skills?: unknown;
  ai_score?: number | null;
  status?: string | null;
  created_at?: string;
}

// ── Support (email + WhatsApp) ─────────────────────────────
export interface EmailThread {
  id: string;
  organization_id: string;
  customer_id?: string | null;
  subject?: string | null;
  participants?: unknown;
  summary?: string | null;
  ai_priority?: string | null;
  category?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface WhatsAppMessage {
  id: string;
  organization_id?: string | null;
  contact_id?: string | null;
  message?: string | null;
  direction?: string | null;
  ai_generated?: boolean | null;
  media?: unknown;
  created_at?: string;
  updated_at?: string;
}

// ── Marketing ──────────────────────────────────────────────
export interface MarketingCampaign {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  campaign_type?: string | null;
  status?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  budget?: number | null;
  created_by?: string | null;
  created_at?: string;
}

// ── Finance (budgets & expenses) ───────────────────────────
export interface Budget {
  id: string;
  organization_id?: string | null;
  name?: string | null;
  amount?: number | null;
  period?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  created_at?: string;
}

export interface Expense {
  id: string;
  organization_id: string;
  category_id?: string | null;
  submitted_by?: string | null;
  title: string;
  description?: string | null;
  amount: number;
  currency?: string | null;
  expense_date?: string | null;
  receipt_url?: string | null;
  status?: string | null;
  approved_by?: string | null;
  created_at?: string;
}

// ── Billing plans (platform catalog) ───────────────────────
export interface Plan {
  id: string;
  name: string;
  description?: string | null;
  price_monthly?: number | null;
  price_yearly?: number | null;
  max_users?: number | null;
  ai_requests_limit?: number | null;
  storage_limit_gb?: number | null;
  features?: unknown;
  active?: boolean | null;
  created_at?: string;
}

// ── CRM activities ─────────────────────────────────────────
export interface Activity {
  id: string;
  organization_id: string;
  user_id?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  action: string;
  metadata?: Record<string, unknown> | null;
  created_at?: string;
}

// ── Departments ────────────────────────────────────────────
export interface OrgDepartment {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  created_at: string;
}

export interface DepartmentCreate {
  name: string;
  description?: string | null;
}

// ── Platform overview (super admin) ───────────────────────
export interface PlatformPlan {
  id: string;
  name: string;
  description?: string | null;
  price_monthly: number | null;
  max_users: number | null;
  ai_requests_limit: number | null;
  storage_limit_gb: number | null;
  active?: boolean | null;
}

export interface PlatformOverview {
  plans: PlatformPlan[];
  aiModels: number;
  integrations: number;
  dashboards: number;
}
