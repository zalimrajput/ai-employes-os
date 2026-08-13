"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarClock, GraduationCap, UserCog, Users } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";
import { fetchCandidates, fetchEmployees, fetchLeaveRequests, initials } from "@/services/business";

function fullName(e: { first_name: string; last_name?: string | null }) {
  return [e.first_name, e.last_name].filter(Boolean).join(" ");
}

export default function HRDashboardPage() {
  const { data: empData, isLoading: employeesLoading } = useQuery({ queryKey: ["employees"], queryFn: fetchEmployees });
  const { data: leaveData } = useQuery({ queryKey: ["leave-requests"], queryFn: fetchLeaveRequests });
  const { data: candidateData } = useQuery({ queryKey: ["candidates"], queryFn: fetchCandidates });

  const employees = empData?.source === "db" ? empData.items : [];
  const leaveRequests = leaveData?.source === "db" ? leaveData.items : [];
  const candidates = candidateData?.source === "db" ? candidateData.items : [];

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="People operations"
        title="HR Dashboard"
        description="Headcount, hiring pipeline, and leave activity at a glance."
        icon={UserCog}
        gradient="from-warning to-danger"
        actions={
          <Link href="/dashboard/chat?agent=hr" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI HR <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Employees" value={String(employees.length)} icon={<Users className="h-5 w-5" />} gradient="from-primary to-secondary" loading={employeesLoading} />
        <StatCard label="Candidates" value={String(candidates.length)} icon={<GraduationCap className="h-5 w-5" />} gradient="from-secondary to-accent" loading={!candidateData} />
        <StatCard label="Leave Requests" value={String(leaveRequests.length)} icon={<CalendarClock className="h-5 w-5" />} gradient="from-warning to-danger" loading={!leaveData} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Team overview — live from the backend */}
        <Card>
          <CardHeader>
            <CardTitle>Team overview</CardTitle>
            <CardDescription>Employee records by department</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {employeesLoading ? (
              <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
            ) : employees.length === 0 ? (
              <p className="text-sm text-slate-500">No employees on record yet.</p>
            ) : (
              employees.slice(0, 6).map((m, i) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  whileHover={{ x: 4 }}
                  className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
                >
                  <div className="flex items-center gap-3">
                    <Avatar name={initials(fullName(m))} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold text-white">{fullName(m)}</p>
                      <p className="truncate text-xs text-slate-500">
                        {m.position ?? m.department_id ?? "No position"} · {m.email ?? "No email"}
                      </p>
                    </div>
                    <Badge variant={m.status === "active" ? "success" : "warning"}>{m.status ?? "active"}</Badge>
                  </div>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Hiring pipeline — live from the backend */}
        <Card>
          <CardHeader>
            <CardTitle>Hiring pipeline</CardTitle>
            <CardDescription>Candidate records in the recruiting module</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!candidateData ? (
              <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
            ) : candidates.length === 0 ? (
              <p className="text-sm text-slate-500">No candidates yet.</p>
            ) : (
              candidates.slice(0, 6).map((h, i) => (
                <motion.div
                  key={h.id}
                  initial={{ opacity: 0, x: 12 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.07 }}
                  whileHover={{ y: -3 }}
                  className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-bold text-white">{h.name ?? "Unnamed candidate"}</p>
                    <Badge variant={h.status === "hired" ? "success" : h.status === "interview" ? "accent" : "secondary"}>{h.status ?? "new"}</Badge>
                  </div>
                  <p className="mt-1.5 text-xs text-slate-500">
                    {h.email ?? "No email"}
                    {h.ai_score != null ? ` · AI score ${h.ai_score}` : ""}
                  </p>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Leave requests — live from the backend */}
      <Card>
        <CardHeader>
          <CardTitle>Leave requests</CardTitle>
          <CardDescription>Latest leave activity</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {!leaveData ? (
            <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : leaveRequests.length === 0 ? (
            <p className="text-sm text-slate-500">No leave requests yet.</p>
          ) : (
            leaveRequests.slice(0, 6).map((l, i) => (
              <motion.div
                key={l.id}
                initial={{ opacity: 0, y: 8 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-warning to-danger">
                  <CalendarClock className="h-4.5 w-4.5 text-white" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-white">{l.leave_type ?? "Leave"}</p>
                  <p className="text-xs text-slate-500">
                    {l.start_date ? `${l.start_date} → ${l.end_date ?? "…"}` : "Dates not set"}
                    {l.reason ? ` · ${l.reason}` : ""}
                  </p>
                </div>
                <Badge variant={l.status === "approved" ? "success" : l.status === "pending" ? "warning" : "secondary"}>
                  {l.status ?? "pending"}
                </Badge>
              </motion.div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="HR Dashboard" />
    </div>
  );
}
