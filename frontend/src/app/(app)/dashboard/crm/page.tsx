"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Heart, UserPlus } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { timeAgo } from "@/lib/utils";
import { fetchActivities, fetchCustomers, fetchLeads, initials } from "@/services/business";
import { motion } from "framer-motion";

export default function CRMDashboardPage() {
  const { data: customersData, isLoading: customersLoading } = useQuery({
    queryKey: ["customers"],
    queryFn: fetchCustomers,
  });
  const { data: leadsData } = useQuery({ queryKey: ["leads"], queryFn: fetchLeads });
  const { data: activitiesData } = useQuery({ queryKey: ["activities"], queryFn: fetchActivities });

  const customers = customersData?.source === "db" ? customersData.items : [];
  const leads = leadsData?.source === "db" ? leadsData.items : [];
  const activities = activitiesData?.source === "db" ? activitiesData.items : [];

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
          icon={<Building2 className="h-5 w-5" />}
          gradient="from-primary to-secondary"
          loading={customersLoading}
        />
        <StatCard
          label="Active Leads"
          value={String(leads.length)}
          icon={<UserPlus className="h-5 w-5" />}
          gradient="from-secondary to-accent"
          loading={!leadsData}
        />
        <StatCard
          label="Recorded Activities"
          value={String(activities.length)}
          icon={<Heart className="h-5 w-5" />}
          gradient="from-accent to-success"
          loading={!activitiesData}
        />
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

        {/* Relationship activity — live from the CRM */}
        <Card>
          <CardHeader>
            <CardTitle>Relationship activity</CardTitle>
            <CardDescription>Latest touches tracked by the CRM</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {!activitiesData ? (
              <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
            ) : activities.length === 0 ? (
              <p className="text-sm text-slate-500">No activity recorded yet.</p>
            ) : (
              activities.slice(0, 6).map((a, i) => (
                <motion.div
                  key={a.id}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  className="flex items-start gap-3 rounded-xl p-3 transition-colors hover:bg-card-soft/60"
                >
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-card-soft text-base">
                    {a.entity_type === "customer" ? "🤝" : a.entity_type === "quotation" ? "📄" : a.entity_type === "invoice" ? "🧾" : "📌"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-200">{a.action}</p>
                    <p className="text-xs text-slate-500">
                      {a.entity_type ?? "note"}{a.created_at ? ` · ${timeAgo(a.created_at)}` : ""}
                    </p>
                  </div>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="CRM Dashboard" />
    </div>
  );
}
