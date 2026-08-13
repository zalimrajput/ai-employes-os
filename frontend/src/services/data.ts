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
 * When a table is empty we return an empty list and the UI shows empty states.
 */

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

export type DataResult<T> =
  | { source: "db"; items: T[] }
  | { source: "error"; error: string };

// ── AI Employees ──────────────────────────────────────────
export async function fetchAIEmployees(): Promise<DataResult<AIEmployee>> {
  const orgId = await getCurrentOrgId();
  let query = supabase.from("ai_employees").select("*").order("created_at", { ascending: true });
  if (orgId) query = query.eq("organization_id", orgId);
  const { data, error } = await query;

  if (error) return { source: "error", error: error.message };
  return { source: "db", items: (data ?? []) as AIEmployee[] };
}

// ── Tasks ─────────────────────────────────────────────────
export async function fetchTasks(): Promise<DataResult<Task>> {
  try {
    const items = await api.fetchTasks();
    return { source: "db", items };
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
    return { source: "db", items: (data ?? []) as Task[] };
  }
}

export async function updateTaskStatus(id: string, status: TaskStatus) {
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
export async function fetchWorkflows(): Promise<DataResult<Workflow>> {
  const orgId = await getCurrentOrgId();
  let query = supabase.from("workflows").select("*").order("created_at", { ascending: false });
  if (orgId) query = query.eq("organization_id", orgId);
  const { data, error } = await query;

  if (error) return { source: "error", error: error.message };
  return { source: "db", items: (data ?? []) as Workflow[] };
}

// ── Conversations & Messages ──────────────────────────────
// Live chat goes through the backend AI engine (org-scoped, real agent
// replies). Direct Supabase is only a fallback when the backend is unreachable.

export async function fetchConversations(): Promise<DataResult<AIConversation>> {
  try {
    const items = await api.fetchAIConversations();
    return { source: "db", items };
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
    return { source: "db", items: (data ?? []) as AIConversation[] };
  }
}

export async function fetchMessages(conversationId: string): Promise<DataResult<AIMessage>> {
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

  const empItems = emp.source === "db" ? emp.items : [];
  const taskItems = tasks.source === "db" ? tasks.items : [];
  const wfItems = wf.source === "db" ? wf.items : [];
  const convItems = conv.source === "db" ? conv.items : [];

  return {
    employees: empItems.length,
    activeEmployees: empItems.filter((e) => e.active !== false).length,
    tasks: taskItems.length,
    workflows: wfItems.length,
    conversations: convItems.length,
    messages: msgs,
  };
}

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
