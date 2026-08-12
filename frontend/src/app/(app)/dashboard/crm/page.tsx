"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Heart, Sparkles, Star, UserPlus } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { timeAgo } from "@/lib/utils";
import { fetchCustomers, fetchLeads, initials } from "@/services/business";
import { motion } from "framer-motion";

const ACTIVITY = [
  { icon: "💬", text: "Acme Corp replied to quotation follow-up", time: "2026-07-31T09:20:00Z" },
  { icon: "📄", text: "GlobalTech signed the SOW proposal", time: "2026-07-31T07:48:00Z" },
  { icon: "📞", text: "Discovery call with Nova Retail completed", time: "2026-07-30T16:30:00Z" },
  { icon: "✉️", text: "Nurture email sent to 12 dormant leads", time: "2026-07-30T11:02:00Z" },
];

export default function CRMDashboardPage() {
  const { data: customersData, isLoading: customersLoading } = useQuery({
    queryKey: ["customers"],
    queryFn: fetchCustomers,
  });
  const { data: leadsData } = useQuery({ queryKey: ["leads"], queryFn: fetchLeads });

  const customers =
    customersData?.source === "db" || customersData?.source === "demo"
      ? customersData.items
      : [];
  const leads = leadsData?.source === "db" || leadsData?.source === "demo" ? leadsData.items : [];

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Relationship intelligence"
        title="CRM Dashboard"
        description="Customer health, lead velocity, and relationship insights across your book of business."
        icon={Heart}
        gradient="from-primary to-accent"
        actions={
          <Link href="/dashboard/chat?agent=sales" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI Sales <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total Customers"
          value={customersLoading ? "—" : String(customers.length)}
          delta={8}
          icon={<Building2 className="h-5 w-5" />}
          gradient="from-primary to-secondary"
          loading={customersLoading}
        />
        <StatCard
          label="Active Leads"
          value={String(leads.length)}
          delta={17}
          icon={<UserPlus className="h-5 w-5" />}
          gradient="from-secondary to-accent"
          loading={!leadsData}
        />
        <StatCard label="Avg. Health Score" value="81" delta={6} icon={<Heart className="h-5 w-5" />} gradient="from-accent to-success" loading={false} />
        <StatCard label="Renewal Rate" value="94%" delta={3} icon={<Star className="h-5 w-5" />} gradient="from-success to-accent" loading={false} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Customer list — live from the backend */}
        <Card>
          <CardHeader>
            <CardTitle>Customers</CardTitle>
            <CardDescription>Accounts in your CRM, ranked by recency</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {customersLoading ? (
              <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div>
            ) : (
              customers.slice(0, 6).map((c, i) => (
                <motion.div
                  key={c.id}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  whileHover={{ x: 4 }}
                  className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
                >
                  <div className="mb-1 flex items-center gap-3">
                    <Avatar name={initials(c.name)} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold text-white">{c.name}</p>
                      <p className="truncate text-xs text-slate-500">
                        {c.email ?? c.phone ?? "No contact"} · {c.company ?? "—"}
                      </p>
                    </div>
                    <Badge variant={c.status === "active" ? "success" : "secondary"}>
                      {c.status ?? "active"}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    Added {c.created_at ? timeAgo(c.created_at) : "recently"}
                  </p>
                </motion.div>
              ))
            )}
            {!customersLoading && customers.length === 0 && (
              <p className="text-sm text-slate-500">No customers yet — create one to see it here.</p>
            )}
          </CardContent>
        </Card>

        {/* Relationship activity */}
        <Card>
          <CardHeader>
            <CardTitle>Relationship activity</CardTitle>
            <CardDescription>Latest touches tracked by the CRM</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {ACTIVITY.map((a, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                className="flex items-start gap-3 rounded-xl p-3 transition-colors hover:bg-card-soft/60"
              >
                <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg bg-card-soft text-base">{a.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-200">{a.text}</p>
                  <p className="text-xs text-slate-500">{timeAgo(a.time)}</p>
                </div>
              </motion.div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* AI insights */}
      <Card>
        <CardHeader className="flex-row items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent">
            <Sparkles className="h-4.5 w-4.5 text-white" />
          </div>
          <div>
            <CardTitle>AI relationship insights</CardTitle>
            <CardDescription>Generated by your AI CRM assistant</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {[
            { title: "Upsell opportunity", body: "GlobalTech usage grew 40% — recommend the Business plan at renewal." },
            { title: "Churn risk", body: "Nova Retail's health dropped 12pts; schedule a check-in call this week." },
            { title: "Expansion signal", body: "BrightLaw uploaded 3 contracts — likely to add seats in Q3." },
          ].map((tip) => (
            <div key={tip.title} className="rounded-xl border border-accent/30 bg-accent/10 p-4">
              <p className="text-sm font-bold text-cyan-300">{tip.title}</p>
              <p className="mt-1 text-sm text-slate-300">{tip.body}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="CRM Dashboard" />
    </div>
  );
}
