"use client";

import { ArrowRight, Clock, Headset, Mail, MessageCircle, ThumbsUp, Zap } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { TasksChart, UsageBars } from "@/components/dashboard/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { timeAgo } from "@/lib/utils";
import { motion } from "framer-motion";

const TICKETS = [
  { id: "TK-2041", subject: "Invoice #1042 not received", channel: "Email", priority: "High", status: "Open", time: "2026-07-31T09:14:00Z" },
  { id: "TK-2040", subject: "Can I get a demo of the API?", channel: "WhatsApp", priority: "Medium", status: "In progress", time: "2026-07-31T08:02:00Z" },
  { id: "TK-2039", subject: "Billing question — plan upgrade", channel: "Email", priority: "Low", status: "Resolved", time: "2026-07-31T06:41:00Z" },
  { id: "TK-2038", subject: "Login issue on mobile", channel: "WhatsApp", priority: "High", status: "Open", time: "2026-07-31T05:55:00Z" },
];

const CHANNELS = [
  { name: "Email", value: 412 },
  { name: "WhatsApp", value: 286 },
  { name: "Live chat", value: 154 },
];

export default function SupportDashboardPage() {
  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Customer care"
        title="Customer Support Dashboard"
        description="Tickets, email and WhatsApp volume, response times, and customer satisfaction."
        icon={Headset}
        gradient="from-accent to-success"
        actions={
          <Link href="/dashboard/chat?agent=support" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI Support <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Open Tickets" value="23" delta={-6} icon={<Headset className="h-5 w-5" />} gradient="from-primary to-secondary" loading={false} />
        <StatCard label="Avg. First Response" value="1.8 min" delta={22} icon={<Zap className="h-5 w-5" />} gradient="from-secondary to-accent" loading={false} />
        <StatCard label="CSAT Score" value="4.7 / 5" delta={3} icon={<ThumbsUp className="h-5 w-5" />} gradient="from-accent to-success" loading={false} />
        <StatCard label="Avg. Resolution" value="4.2 hrs" delta={12} icon={<Clock className="h-5 w-5" />} gradient="from-success to-accent" loading={false} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Support queue</CardTitle>
            <CardDescription>Latest tickets across email and WhatsApp</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {TICKETS.map((t, i) => (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                whileHover={{ x: 4 }}
                className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-card-soft">
                  {t.channel === "WhatsApp" ? <MessageCircle className="h-4 w-4 text-cyan-400" /> : <Mail className="h-4 w-4 text-primary-soft" />}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-white">{t.subject}</p>
                  <p className="text-xs text-slate-500">{t.id} · {t.channel} · {timeAgo(t.time)}</p>
                </div>
                <Badge variant={t.priority === "High" ? "danger" : t.priority === "Medium" ? "warning" : "secondary"}>{t.priority}</Badge>
                <Badge variant={t.status === "Resolved" ? "success" : t.status === "In progress" ? "accent" : "default"}>{t.status}</Badge>
              </motion.div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Volume by channel</CardTitle>
              <CardDescription>Conversations handled this week</CardDescription>
            </CardHeader>
            <CardContent><UsageBars data={CHANNELS} /></CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Tickets per day</CardTitle>
              <CardDescription>Inbound support volume</CardDescription>
            </CardHeader>
            <CardContent><TasksChart /></CardContent>
          </Card>
        </div>
      </div>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Customer Support Dashboard" />
    </div>
  );
}
