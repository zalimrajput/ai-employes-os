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
