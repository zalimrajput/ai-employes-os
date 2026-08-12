"use client";

import { ArrowRight, CalendarClock, GraduationCap, UserCheck, UserCog, Users } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Avatar } from "@/components/ui/avatar";
import { motion } from "framer-motion";

const TEAM = [
  { name: "Alex Morgan", dept: "Engineering", status: "Active", attendance: 96, initials: "AM" },
  { name: "Priya Sharma", dept: "Sales", status: "Active", attendance: 92, initials: "PS" },
  { name: "Jamie Lee", dept: "Marketing", status: "On leave", attendance: 61, initials: "JL" },
  { name: "Sam Rivera", dept: "Finance", status: "Active", attendance: 98, initials: "SR" },
];

const HIRING = [
  { role: "Senior Full-Stack Engineer", stage: "Interview", candidates: 6, days: 4 },
  { role: "Customer Success Manager", stage: "Offer", candidates: 3, days: 2 },
  { role: "Marketing Designer", stage: "Review", candidates: 9, days: 7 },
];

export default function HRDashboardPage() {
  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="People operations"
        title="HR Dashboard"
        description="Headcount, attendance, hiring pipeline, and team well-being at a glance."
        icon={UserCog}
        gradient="from-warning to-danger"
        actions={
          <Link href="/dashboard/chat?agent=hr" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI HR <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Employees" value="48" delta={5} icon={<Users className="h-5 w-5" />} gradient="from-primary to-secondary" loading={false} />
        <StatCard label="Attendance (avg)" value="94%" delta={2} icon={<UserCheck className="h-5 w-5" />} gradient="from-secondary to-accent" loading={false} />
        <StatCard label="Open Roles" value="7" delta={-1} icon={<GraduationCap className="h-5 w-5" />} gradient="from-accent to-success" loading={false} />
        <StatCard label="On Leave Today" value="3" delta={0} icon={<CalendarClock className="h-5 w-5" />} gradient="from-warning to-danger" loading={false} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Team overview</CardTitle>
            <CardDescription>Attendance and status by team member</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {TEAM.map((m, i) => (
              <motion.div
                key={m.name}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                whileHover={{ x: 4 }}
                className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
              >
                <div className="mb-2 flex items-center gap-3">
                  <Avatar name={m.initials} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{m.name}</p>
                    <p className="truncate text-xs text-slate-500">{m.dept}</p>
                  </div>
                  <Badge variant={m.status === "Active" ? "success" : "warning"}>{m.status}</Badge>
                </div>
                <Progress value={m.attendance} barClassName={m.attendance >= 90 ? "from-success to-accent" : "from-warning to-amber-500"} />
                <p className="mt-1 text-xs text-slate-500">Attendance: <span className="font-semibold text-white">{m.attendance}%</span></p>
              </motion.div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Hiring pipeline</CardTitle>
            <CardDescription>Active recruitment across open roles</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {HIRING.map((h, i) => (
              <motion.div
                key={h.role}
                initial={{ opacity: 0, x: 12 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.07 }}
                whileHover={{ y: -3 }}
                className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-bold text-white">{h.role}</p>
                  <Badge variant={h.stage === "Offer" ? "accent" : h.stage === "Interview" ? "default" : "secondary"}>{h.stage}</Badge>
                </div>
                <p className="mt-1.5 text-xs text-slate-500">{h.candidates} candidates · {h.days} days in stage</p>
                <Progress value={h.stage === "Offer" ? 90 : h.stage === "Interview" ? 60 : 35} className="mt-2" />
              </motion.div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="HR Dashboard" />
    </div>
  );
}
