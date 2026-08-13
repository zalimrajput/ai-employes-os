"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarClock, Gauge, ListChecks, Workflow as WorkflowIcon } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, StatusDot } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchMeetings } from "@/services/business";
import { fetchTasks, fetchWorkflows } from "@/services/data";
import { formatTime } from "@/lib/utils";
import { motion } from "framer-motion";

export default function OperationsDashboardPage() {
  const { data: meetingsData, isLoading: meetingsLoading } = useQuery({
    queryKey: ["meetings"],
    queryFn: fetchMeetings,
  });
  const { data: workflowsData, isLoading: workflowsLoading } = useQuery({
    queryKey: ["workflows"],
    queryFn: fetchWorkflows,
  });
  const { data: tasksData } = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });

  const meetings = meetingsData?.source === "db" ? meetingsData.items : [];
  const workflows = workflowsData?.source === "db" ? workflowsData.items : [];
  const tasks = tasksData?.source === "db" ? tasksData.items : [];

  const activeWorkflows = workflows.filter((w) => w.active !== false).length;
  const openTasks = tasks.filter((t) => (t.status ?? "") !== "done").length;

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Operational command"
        title="Operations Dashboard"
        description="Workflow health, task throughput, and the operational queue across the company."
        icon={Gauge}
        gradient="from-warning to-accent"
        actions={
          <>
            <Link href="/dashboard/chat?agent=inventory" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
              Ask AI Operations <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/dashboard/workflows" className="inline-flex items-center gap-1.5 rounded-xl border border-border-soft bg-card-soft/60 px-4 py-2.5 text-sm font-bold text-slate-200 transition-all hover:bg-card-soft">
              Manage workflows
            </Link>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Workflows" value={String(workflows.length)} icon={<WorkflowIcon className="h-5 w-5" />} gradient="from-primary to-secondary" loading={workflowsLoading} />
        <StatCard label="Active Workflows" value={String(activeWorkflows)} icon={<Gauge className="h-5 w-5" />} gradient="from-secondary to-accent" loading={workflowsLoading} />
        <StatCard label="Tasks" value={String(tasks.length)} icon={<ListChecks className="h-5 w-5" />} gradient="from-accent to-success" loading={!tasksData} />
        <StatCard label="Open Tasks" value={String(openTasks)} icon={<CalendarClock className="h-5 w-5" />} gradient="from-warning to-danger" loading={!tasksData} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Upcoming meetings — live from the calendar module */}
        <Card>
          <CardHeader>
            <CardTitle>Upcoming meetings</CardTitle>
            <CardDescription>Live from the calendar module</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {meetingsLoading ? (
              <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
            ) : meetings.length === 0 ? (
              <p className="text-sm text-slate-500">No meetings scheduled yet.</p>
            ) : (
              meetings.slice(0, 6).map((m, i) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
                >
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent">
                    <CalendarClock className="h-4.5 w-4.5 text-white" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{m.title ?? "Untitled meeting"}</p>
                    <p className="text-xs text-slate-500">{m.start_time ? formatTime(m.start_time) : "No time set"}</p>
                  </div>
                  <Badge variant="secondary">Scheduled</Badge>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Workflows — live from the automation engine */}
        <Card>
          <CardHeader>
            <CardTitle>Workflows</CardTitle>
            <CardDescription>Automations in your workspace</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {workflowsLoading ? (
              <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
            ) : workflows.length === 0 ? (
              <p className="text-sm text-slate-500">No workflows yet — create one to see it here.</p>
            ) : (
              workflows.slice(0, 6).map((w, i) => (
                <motion.div
                  key={w.id}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <p className="text-sm font-bold text-white">{w.name ?? "Untitled workflow"}</p>
                    <Badge variant={w.active === false ? "secondary" : "success"}>
                      <StatusDot color={w.active === false ? "#64748b" : "#22c55e"} />
                      {w.active === false ? "Paused" : "Active"}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    Trigger: {String((w.trigger as Record<string, unknown> | null)?.event ?? "manual")}
                    {" · "}
                    {Array.isArray(w.actions) ? (w.actions as unknown[]).length : 0} action(s)
                  </p>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Operational queue — live tasks */}
      <Card>
        <CardHeader>
          <CardTitle>Task queue</CardTitle>
          <CardDescription>Work items in your task board</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {!tasksData ? (
            <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : tasks.length === 0 ? (
            <p className="text-sm text-slate-500">No tasks yet.</p>
          ) : (
            tasks.slice(0, 8).map((t, i) => (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                whileHover={{ x: 4 }}
                className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-card-soft text-slate-300">#{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-white">{t.title}</p>
                  <p className="text-xs text-slate-500">{t.priority ?? "no priority"}</p>
                </div>
                <Badge variant={t.status === "done" ? "success" : t.status === "in_progress" ? "accent" : "secondary"}>
                  {t.status?.replace("_", " ") ?? "todo"}
                </Badge>
              </motion.div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Operations Dashboard" />
    </div>
  );
}
