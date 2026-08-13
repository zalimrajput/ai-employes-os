"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, CalendarClock, CheckCircle2, MessageSquare, Sparkles, Target } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchAIEmployees, fetchTasks, PRIORITY_COLORS } from "@/services/data";
import { fetchMeetings } from "@/services/business";
import { useSession } from "@/hooks/use-session";
import { formatDate, formatTime, timeAgo } from "@/lib/utils";
import { motion } from "framer-motion";

export default function EmployeeDashboardPage() {
  const { data: session } = useSession();
  const { data: empData } = useQuery({ queryKey: ["ai-employees"], queryFn: fetchAIEmployees });
  const { data: taskData } = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });
  const { data: meetingsData, isLoading: meetingsLoading } = useQuery({
    queryKey: ["meetings"],
    queryFn: fetchMeetings,
  });

  const employees = empData?.source === "db" ? empData.items : [];
  const tasks = taskData?.source === "db" ? taskData.items : [];
  const myTasks = tasks.slice(0, 4);
  const completed = tasks.filter((t) => t.status === "done").length;
  const deadlines = tasks
    .filter((t) => t.due_date)
    .slice(0, 4);
  const meetings = meetingsData?.source === "db" ? meetingsData.items : [];

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="My workspace"
        title={`Welcome, ${session?.user?.name ?? "there"}`}
        description="Your personal tasks, deadlines, and the AI assistants ready to help you today."
        icon={Sparkles}
        gradient="from-primary to-success"
        actions={
          <Link href="/dashboard/chat?agent=executive" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            <MessageSquare className="h-4 w-4" /> Ask AI
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="My Tasks" value={String(myTasks.length)} icon={<Target className="h-5 w-5" />} gradient="from-primary to-secondary" loading={!taskData} />
        <StatCard label="Completed" value={String(completed)} icon={<CheckCircle2 className="h-5 w-5" />} gradient="from-secondary to-accent" loading={!taskData} />
        <StatCard label="Meetings Today" value={meetingsLoading ? "—" : String(meetings.length)} icon={<CalendarClock className="h-5 w-5" />} gradient="from-accent to-success" loading={meetingsLoading} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>My tasks</CardTitle>
              <CardDescription>Work assigned to you</CardDescription>
            </div>
            <Link href="/dashboard/tasks" className="inline-flex items-center gap-1 text-sm font-semibold text-primary-soft hover:text-white transition-colors">
              Open board <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {myTasks.length === 0 ? (
              <p className="text-sm text-slate-500">No tasks assigned yet.</p>
            ) : (
              myTasks.map((t, i) => (
                <motion.div
                  key={t.id}
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  whileHover={{ x: 4 }}
                  className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
                >
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: PRIORITY_COLORS[t.priority ?? "medium"] }} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-100">{t.title}</p>
                    <p className="text-xs text-slate-500">{t.description ?? "No description"} · {timeAgo(t.due_date ?? t.created_at)}</p>
                  </div>
                  <Badge variant={t.status === "done" ? "success" : t.status === "in_progress" ? "accent" : "secondary"}>
                    {t.status?.replace("_", " ")}
                  </Badge>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Today&apos;s schedule</CardTitle>
            <CardDescription>{formatDate(new Date())}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {meetings.length === 0 ? (
              <p className="text-sm text-slate-500">Nothing on the calendar yet.</p>
            ) : (
              meetings.slice(0, 6).map((m, i) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-3 rounded-xl p-2.5 transition-colors hover:bg-card-soft/60"
                >
                  <span className="w-14 text-xs font-bold text-primary-soft">
                    {m.start_time ? formatTime(m.start_time) : "—"}
                  </span>
                  <span className="text-base">🗓️</span>
                  <span className="truncate text-sm font-medium text-slate-200">
                    {m.title ?? "Untitled meeting"}
                  </span>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Upcoming deadlines — live tasks with due dates */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Upcoming deadlines</CardTitle>
            <CardDescription>Next due dates on your plate</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {deadlines.length === 0 ? (
              <p className="text-sm text-slate-500">No deadlines coming up.</p>
            ) : (
              deadlines.map((d, i) => (
                <motion.div
                  key={d.id}
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  whileHover={{ y: -3 }}
                  className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-bold text-white">{d.title}</p>
                    <Badge variant={d.priority === "high" ? "danger" : d.priority === "medium" ? "warning" : "secondary"}>{d.priority ?? "low"}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">Due {formatDate(d.due_date)}</p>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>My AI assistants</CardTitle>
            <CardDescription>Agents ready to take work off your plate</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {employees.slice(0, 4).map((e, i) => (
              <motion.div
                key={e.id}
                initial={{ opacity: 0, x: 10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                whileHover={{ x: 4 }}
                className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-secondary">
                  <Bot className="h-4.5 w-4.5 text-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-white">{e.name}</p>
                  <p className="truncate text-xs text-slate-500">{e.description}</p>
                </div>
                <Link href={`/dashboard/chat?employee=${e.id}`}>
                  <Badge variant="accent" className="cursor-pointer">Chat</Badge>
                </Link>
              </motion.div>
            ))}
            {employees.length === 0 && (
              <p className="text-sm text-slate-500">No AI employees deployed yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Employee Dashboard" />
    </div>
  );
}
