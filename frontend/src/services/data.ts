import { supabase } from "@/lib/supabase/client";
import { api } from "@/lib/api/client";
import type {
  AIEmployee,
  AIConversation,
  AIMessage,
  OrgStats,
  Task,
  TaskPriority,
  TaskStatus,
  Workflow,
} from "@/lib/api/types";

/**
 * Data-access helpers backed by the real Supabase database.
 * Queries use RLS: the signed-in user only sees their organization's rows.
 * When a table is empty (fresh workspace) we return curated demo rows so
 * the UI is always alive, flagged via `source: "demo"`.
 */

/**
 * Demo mode is opt-in via NEXT_PUBLIC_ENABLE_DEMO=true (dev/preview only).
 * In production, empty workspaces return empty lists instead of curated fake
 * rows so real customers never see demo data.
 */
export function isDemoEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ENABLE_DEMO === "true";
}

async function getCurrentOrgId(): Promise<string | null> {
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;
  const { data } = await supabase
    .from("users")
    .select("organization_id")
    .eq("id", user.id)
    .maybeSingle();
  return (data?.organization_id as string) ?? null;
}

// ── AI Employees ──────────────────────────────────────────
export async function fetchAIEmployees(): Promise<
  { source: "db" | "demo"; items: AIEmployee[] } | { source: "error"; error: string }
> {
  const orgId = await getCurrentOrgId();
  let query = supabase.from("ai_employees").select("*").order("created_at", { ascending: true });
  if (orgId) query = query.eq("organization_id", orgId);
  const { data, error } = await query;

  if (error) return { source: "error", error: error.message };
  if (data && data.length > 0) return { source: "db", items: data as AIEmployee[] };

  return isDemoEnabled()
    ? { source: "demo", items: DEMO_EMPLOYEES }
    : { source: "db", items: [] };
}

// ── Tasks ─────────────────────────────────────────────────
export async function fetchTasks(): Promise<
  { source: "db" | "demo"; items: Task[] } | { source: "error"; error: string }
> {
  try {
    const items = await api.fetchTasks();
    if (items.length > 0) return { source: "db", items };
    return isDemoEnabled()
      ? { source: "demo", items: DEMO_TASKS }
      : { source: "db", items: [] };
  } catch (err) {
    const message = (err as Error).message ?? "";
    // Only fall back to direct Supabase when the backend is unreachable —
    // real server errors (403/500) must surface.
    if (!message.includes("Could not reach the backend")) {
      return { source: "error", error: message };
    }
    const orgId = await getCurrentOrgId();
    let query = supabase.from("tasks").select("*").order("created_at", { ascending: false });
    if (orgId) query = query.eq("organization_id", orgId);
    const { data, error } = await query;
    if (error) return { source: "error", error: error.message };
    if (data && data.length > 0) return { source: "db", items: data as Task[] };
    return isDemoEnabled()
      ? { source: "demo", items: DEMO_TASKS }
      : { source: "db", items: [] };
  }
}

export async function updateTaskStatus(id: string, status: TaskStatus) {
  // Demo rows are UI-only; live rows go through the backend PATCH endpoint.
  if (id.startsWith("demo-")) return { error: null };
  try {
    await api.updateTask(id, { status });
    return { error: null };
  } catch (err) {
    const message = (err as Error).message ?? "";
    if (!message.includes("Could not reach the backend")) {
      return { error: message };
    }
    const { error } = await supabase.from("tasks").update({ status }).eq("id", id);
    return { error: error?.message ?? null };
  }
}

export async function createTask(input: {
  title: string;
  description?: string | null;
  priority?: TaskPriority;
  status?: TaskStatus;
  due_date?: string | null;
}): Promise<{ error: string | null }> {
  try {
    await api.createTask(input);
    return { error: null };
  } catch (err) {
    const message = (err as Error).message ?? "";
    if (!message.includes("Could not reach the backend")) {
      return { error: message };
    }
    const orgId = await getCurrentOrgId();
    const { error } = await supabase.from("tasks").insert({
      ...input,
      organization_id: orgId ?? undefined,
    });
    return { error: error?.message ?? null };
  }
}

// ── Workflows ─────────────────────────────────────────────
export async function fetchWorkflows(): Promise<
  { source: "db" | "demo"; items: Workflow[] } | { source: "error"; error: string }
> {
  const orgId = await getCurrentOrgId();
  let query = supabase.from("workflows").select("*").order("created_at", { ascending: false });
  if (orgId) query = query.eq("organization_id", orgId);
  const { data, error } = await query;

  if (error) return { source: "error", error: error.message };
  if (data && data.length > 0) return { source: "db", items: data as Workflow[] };

  return isDemoEnabled()
    ? { source: "demo", items: DEMO_WORKFLOWS }
    : { source: "db", items: [] };
}

// ── Conversations & Messages ──────────────────────────────
// Live chat goes through the backend AI engine (org-scoped, real agent
// replies). Direct Supabase is only a fallback when the backend is unreachable,
// and demo rows only appear for pre-seeded `demo-` conversations.

function isDemoConversation(id: string) {
  return id.startsWith("demo-");
}

export async function fetchConversations(): Promise<
  { source: "db" | "demo"; items: AIConversation[] } | { source: "error"; error: string }
> {
  try {
    const items = await api.fetchAIConversations();
    if (items.length > 0) return { source: "db", items };
    return isDemoEnabled()
      ? { source: "demo", items: DEMO_CONVERSATIONS }
      : { source: "db", items: [] };
  } catch (err) {
    const message = (err as Error).message ?? "";
    // Only fall back to direct Supabase when the backend is unreachable —
    // real server errors (401/403/500) must surface.
    if (!message.includes("Could not reach the backend")) {
      return { source: "error", error: message };
    }
    const orgId = await getCurrentOrgId();
    let query = supabase
      .from("ai_conversations")
      .select("*")
      .order("updated_at", { ascending: false });
    if (orgId) query = query.eq("organization_id", orgId);
    const { data, error } = await query;
    if (error) return { source: "error", error: error.message };
    if (data && data.length > 0) return { source: "db", items: data as AIConversation[] };
    return isDemoEnabled()
      ? { source: "demo", items: DEMO_CONVERSATIONS }
      : { source: "db", items: [] };
  }
}

export async function fetchMessages(conversationId: string): Promise<
  { source: "db" | "demo"; items: AIMessage[] } | { source: "error"; error: string }
> {
  // Demo conversations are UI-only — show their curated demo thread.
  if (isDemoConversation(conversationId) && isDemoEnabled()) {
    return { source: "demo", items: DEMO_MESSAGES };
  }
  try {
    const items = await api.fetchAIMessages(conversationId);
    return { source: "db", items };
  } catch (err) {
    const message = (err as Error).message ?? "";
    if (!message.includes("Could not reach the backend")) {
      return { source: "error", error: message };
    }
    const { data, error } = await supabase
      .from("ai_messages")
      .select("*")
      .eq("conversation_id", conversationId)
      .order("created_at", { ascending: true });
    if (error) return { source: "error", error: error.message };
    return { source: "db", items: (data ?? []) as AIMessage[] };
  }
}

export async function createConversation(input: {
  organization_id: string;
  user_id: string;
  ai_employee_id: string;
  title: string;
}): Promise<AIConversation | null> {
  try {
    const conv = await api.createAIConversation({
      ai_employee_id: input.ai_employee_id,
      title: input.title,
    });
    return conv as AIConversation;
  } catch (err) {
    const message = (err as Error).message ?? "";
    if (!message.includes("Could not reach the backend")) {
      return null;
    }
    const { data, error } = await supabase
      .from("ai_conversations")
      .insert(input)
      .select()
      .single();
    return error ? null : (data as AIConversation);
  }
}


// ── Org stats for dashboard/analytics ─────────────────────
export async function fetchOrgStats(): Promise<OrgStats> {
  const [emp, tasks, wf, conv, msgs] = await Promise.all([
    fetchAIEmployees(),
    fetchTasks(),
    fetchWorkflows(),
    fetchConversations(),
    (async () => {
      const { count } = await supabase.from("ai_messages").select("*", { count: "exact", head: true });
      return count ?? 0;
    })(),
  ]);

  const empItems = emp.source === "demo" ? emp.items : emp.source === "db" ? emp.items : [];
  const taskItems = tasks.source === "demo" ? tasks.items : tasks.source === "db" ? tasks.items : [];
  const wfItems = wf.source === "demo" ? wf.items : wf.source === "db" ? wf.items : [];
  const convItems =
    conv.source === "demo" ? conv.items : conv.source === "db" ? conv.items : [];

  return {
    employees: empItems.length,
    activeEmployees: empItems.filter((e) => e.active !== false).length,
    tasks: taskItems.length,
    workflows: wfItems.length,
    conversations: convItems.length,
    messages: msgs || (conv.source === "demo" ? DEMO_MESSAGES.length : 0),
  };
}

// ── Demo data (fresh workspaces) ──────────────────────────
export const DEMO_EMPLOYEES: AIEmployee[] = [
  {
    id: "demo-emp-1",
    organization_id: "",
    name: "Marketing GPT",
    role: "Marketing Assistant",
    description: "Creates campaigns, drafts social posts, and tracks brand sentiment.",
    model: "gpt-5",
    active: true,
  },
  {
    id: "demo-emp-2",
    organization_id: "",
    name: "Sales Assistant",
    role: "Sales Manager",
    description: "Qualifies leads, follows up, and drafts quotations automatically.",
    model: "gpt-5",
    active: true,
  },
  {
    id: "demo-emp-3",
    organization_id: "",
    name: "Support Hero",
    role: "Customer Support Agent",
    description: "Resolves tickets, answers FAQs, and escalates with full context.",
    model: "claude-4",
    active: true,
  },
  {
    id: "demo-emp-4",
    organization_id: "",
    name: "Finance Bot",
    role: "Finance Assistant",
    description: "Tracks invoices, chases payments, and forecasts cash flow.",
    model: "gpt-5",
    active: false,
  },
  {
    id: "demo-emp-5",
    organization_id: "",
    name: "HR Helper",
    role: "HR Assistant",
    description: "Drafts offers, schedules interviews, and answers policy questions.",
    model: "gpt-5",
    active: true,
  },
  {
    id: "demo-emp-6",
    organization_id: "",
    name: "Executive Assistant",
    role: "CEO Assistant",
    description: "Manages calendars, prepares briefings, and summarizes meetings.",
    model: "gpt-5",
    active: true,
  },
];

export const DEMO_TASKS: Task[] = [
  { id: "demo-t1", title: "Send quotation to Acme Corp", description: "25 laptops — follow pricing sheet", priority: "high", status: "todo", ai_created: true },
  { id: "demo-t2", title: "Draft weekly sales report", description: "Summarize pipeline movement", priority: "medium", status: "in_progress", ai_created: true },
  { id: "demo-t3", title: "Follow up with GlobalTech", description: "No reply in 3 days — nudge email", priority: "urgent", status: "in_progress", ai_created: true },
  { id: "demo-t4", title: "Summarize Monday standup", description: "Extract action items", priority: "low", status: "review", ai_created: true },
  { id: "demo-t5", title: "Update CRM pipeline", description: "Move won deals to closed stage", priority: "medium", status: "done", ai_created: true },
  { id: "demo-t6", title: "Prepare invoice for invoice #1042", description: "Attach line items from quotation", priority: "high", status: "done", ai_created: true },
];

export const DEMO_WORKFLOWS: Workflow[] = [
  {
    id: "demo-w1",
    name: "Customer pays invoice",
    trigger: { event: "invoice.paid" },
    actions: [
      { type: "generate_receipt" },
      { type: "update_crm" },
      { type: "notify_sales" },
      { type: "send_thank_you_email" },
      { type: "schedule_follow_up" },
    ],
    active: true,
  },
  {
    id: "demo-w2",
    name: "New lead captured",
    trigger: { event: "lead.created" },
    actions: [
      { type: "classify_lead" },
      { type: "create_task" },
      { type: "send_welcome_email" },
    ],
    active: true,
  },
  {
    id: "demo-w3",
    name: "Invoice overdue reminder",
    trigger: { event: "invoice.overdue" },
    actions: [{ type: "send_reminder" }, { type: "notify_finance" }],
    active: false,
  },
];

export const DEMO_CONVERSATIONS: AIConversation[] = [
  {
    id: "demo-c1",
    organization_id: "",
    user_id: "",
    ai_employee_id: "demo-emp-1",
    title: "Q3 launch campaign",
    status: "active",
  },
  {
    id: "demo-c2",
    organization_id: "",
    user_id: "",
    ai_employee_id: "demo-emp-2",
    title: "Acme Corp quotation",
    status: "active",
  },
];

export const DEMO_MESSAGES: AIMessage[] = [
  {
    id: "demo-m1",
    conversation_id: "demo-c1",
    role: "user",
    message: "Draft a launch announcement for our new AI workspace product.",
  },
  {
    id: "demo-m2",
    conversation_id: "demo-c1",
    role: "assistant",
    message:
      "Here's a draft:\n\n**🚀 Introducing AI Employee OS**\n\nYour business now runs with an AI workforce. Emails, quotations, CRM, reports — handled by specialized AI employees that actually *do* the work.\n\nWant me to post it to LinkedIn and X, and schedule A/B variants?",
  },
];

// priority + status presentation helpers
export const PRIORITY_COLORS: Record<TaskPriority, string> = {
  low: "#94a3b8",
  medium: "#f59e0b",
  high: "#ef4444",
  urgent: "#dc2626",
};

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To Do",
  in_progress: "In Progress",
  review: "In Review",
  done: "Done",
};

export const TASK_STATUSES: TaskStatus[] = ["todo", "in_progress", "review", "done"];
