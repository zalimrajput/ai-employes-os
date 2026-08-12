"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarClock, CheckCircle2, Clock, Gauge, Workflow as WorkflowIcon, Zap } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { EfficiencyChart, TasksChart } from "@/components/dashboard/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, StatusDot } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchMeetings } from "@/services/business";
import { formatTime } from "@/lib/utils";
import { motion } from "framer-motion";

const AUTOMATIONS = [
  { name: "Customer pays invoice", runs: 1284, success: 99.2, active: true },
  { name: "New lead captured", runs: 842, success: 97.8, active: true },
  { name: "Invoice overdue reminder", runs: 396, success: 96.1, active: true },
  { name: "Weekly report digest", runs: 148, success: 100, active: false },
];

const QUEUE = [
  { task: "Approve quotation for GlobalTech", assignee: "Priya Sharma", status: "Awaiting approval", time: "20m" },
  { task: "Review support escalation TK-2038", assignee: "Jamie Lee", status: "In review", time: "1h" },
  { task: "Validate expense report #512", assignee: "Sam Rivera", status: "Pending", time: "3h" },
  { task: "Publish marketing digest draft", assignee: "Alex Morgan", status: "Scheduled", time: "5h" },
];

export default function OperationsDashboardPage() {
  const { data: meetingsData, isLoading: meetingsLoading } = useQuery({
    queryKey: ["meetings"],
    queryFn: fetchMeetings,
  });

  const meetings =
    meetingsData?.source === "db" || meetingsData?.source === "demo"
      ? meetingsData.items
      : [];

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Operational command"
        title="Operations Dashboard"
        description="Automation health, task throughput, and the operational queue across the company."
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
        <StatCard label="Automation Runs" value="2,670" delta={21} icon={<Zap className="h-5 w-5" />} gradient="from-primary to-secondary" loading={false} />
        <StatCard label="Success Rate" value="98.2%" delta={1} icon={<CheckCircle2 className="h-5 w-5" />} gradient="from-secondary to-accent" loading={false} />
        <StatCard label="Active Workflows" value="14" delta={3} icon={<WorkflowIcon className="h-5 w-5" />} gradient="from-accent to-success" loading={false} />
        <StatCard label="Avg. Cycle Time" value="3.2 hrs" delta={9} icon={<Clock className="h-5 w-5" />} gradient="from-warning to-danger" loading={false} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
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

        <Card>
          <CardHeader>
            <CardTitle>Automation health</CardTitle>
            <CardDescription>Workflow runs and success rates</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {AUTOMATIONS.map((a, i) => (
              <motion.div
                key={a.name}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
              >
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-bold text-white">{a.name}</p>
                  <Badge variant={a.active ? "success" : "secondary"}>
                    <StatusDot color={a.active ? "#22c55e" : "#64748b"} />
                    {a.active ? "Active" : "Paused"}
                  </Badge>
                </div>
                <div className="flex items-center gap-3">
                  <Progress value={a.success} className="flex-1" />
                  <span className="text-xs font-bold text-white">{a.success}%</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{a.runs.toLocaleString()} runs · automation engine</p>
              </motion.div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Automation efficiency</CardTitle>
              <CardDescription>Share of operations handled by AI</CardDescription>
            </CardHeader>
            <CardContent><EfficiencyChart /></CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Task throughput</CardTitle>
              <CardDescription>Completed per day</CardDescription>
            </CardHeader>
            <CardContent><TasksChart /></CardContent>
          </Card>
        </div>
      </div>

      {/* Operational queue */}
      <Card>
        <CardHeader>
          <CardTitle>Operational queue</CardTitle>
          <CardDescription>Items waiting on human approval or review</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {QUEUE.map((q, i) => (
            <motion.div
              key={q.task}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ x: 4 }}
              className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-card-soft text-slate-300">#{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-white">{q.task}</p>
                <p className="text-xs text-slate-500">{q.assignee}</p>
              </div>
              <Badge variant="secondary">{q.status}</Badge>
              <span className="text-xs text-slate-500">{q.time}</span>
            </motion.div>
          ))}
        </CardContent>
      </Card>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Operations Dashboard" />
    </div>
  );
}
