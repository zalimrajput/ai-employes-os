"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, DollarSign, FileText, Target, TrendingUp, Users } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { UsageBars } from "@/components/dashboard/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";
import { currency, fetchLeads, fetchQuotations, initials } from "@/services/business";

const STAGE_COLORS: Record<string, string> = {
  lead: "#94a3b8",
  qualified: "#06b6d4",
  proposal: "#6366f1",
  negotiation: "#7c3aed",
  sent: "#6366f1",
  approved: "#22c55e",
  won: "#22c55e",
  lost: "#ef4444",
};

export default function SalesDashboardPage() {
  const { data: quotesData, isLoading: quotesLoading } = useQuery({
    queryKey: ["quotations"],
    queryFn: fetchQuotations,
  });
  const { data: leadsData } = useQuery({ queryKey: ["leads"], queryFn: fetchLeads });

  const quotations = quotesData?.source === "db" ? quotesData.items : [];
  const leads = leadsData?.source === "db" ? leadsData.items : [];

  const pipelineValue = quotations.reduce((acc, q) => acc + Number(q.total ?? 0), 0);
  const sentCount = quotations.filter(
    (q) => !["approved", "won", "lost"].includes((q.status ?? "").toLowerCase())
  ).length;

  // Outreach by channel, derived from live quotation statuses.
  const statusCounts = new Map<string, number>();
  for (const q of quotations) {
    const key = (q.status ?? "draft").toLowerCase();
    statusCounts.set(key, (statusCounts.get(key) ?? 0) + 1);
  }
  const channelBars = [...statusCounts.entries()].map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
  }));

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Revenue engine"
        title="Sales Dashboard"
        description="Pipeline movement, lead velocity, and quotation performance across the sales team."
        icon={TrendingUp}
        gradient="from-success to-accent"
        actions={
          <Link href="/dashboard/chat?agent=sales" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Delegate follow-ups <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Pipeline Value" value={currency(pipelineValue)} icon={<DollarSign className="h-5 w-5" />} gradient="from-success to-accent" loading={quotesLoading} />
        <StatCard label="Active Leads" value={String(leads.length)} icon={<Users className="h-5 w-5" />} gradient="from-primary to-secondary" loading={!leadsData} />
        <StatCard label="Quotations" value={String(quotations.length)} icon={<FileText className="h-5 w-5" />} gradient="from-secondary to-accent" loading={quotesLoading} />
        <StatCard label="Sent / Pending" value={String(sentCount)} icon={<Target className="h-5 w-5" />} gradient="from-accent to-success" loading={quotesLoading} />
      </div>

      {/* Quotations by status */}
      <Card>
        <CardHeader>
          <CardTitle>Quotations by status</CardTitle>
          <CardDescription>Live from the sales module</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {quotesLoading ? (
            <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-8" />)}</div>
          ) : quotations.length === 0 ? (
            <p className="text-sm text-slate-500">No quotations yet — create one to see it here.</p>
          ) : (
            [...statusCounts.entries()].map(([stage, count], i) => (
              <motion.div
                key={stage}
                initial={{ opacity: 0, x: -12 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                className="flex items-center gap-4"
              >
                <span className="w-28 text-sm font-semibold capitalize text-slate-200">{stage}</span>
                <div className="flex-1">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-card-soft">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${quotations.length ? (count / quotations.length) * 100 : 0}%`,
                        backgroundColor: STAGE_COLORS[stage] ?? "#6366f1",
                      }}
                    />
                  </div>
                </div>
                <span className="w-16 text-right text-sm font-bold text-white">{count}</span>
              </motion.div>
            ))
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Deals in flight</CardTitle>
            <CardDescription>Live leads from the CRM</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!leadsData ? (
              <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
            ) : (
              leads.slice(0, 6).map((l) => (
                <div key={l.id} className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3">
                  <Avatar name={initials(l.name)} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{l.name ?? "Unnamed lead"}</p>
                    <p className="truncate text-xs text-slate-500">{l.email ?? l.company ?? "—"}</p>
                  </div>
                  <Badge variant={l.status === "Negotiation" ? "default" : l.status === "Proposal" ? "accent" : "secondary"}>
                    {l.status ?? "Lead"}
                  </Badge>
                  {l.value && <span className="text-sm font-bold text-white">{l.value}</span>}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Status distribution</CardTitle>
            <CardDescription>Live distribution of the pipeline</CardDescription>
          </CardHeader>
          <CardContent>{channelBars.length > 0 ? <UsageBars data={channelBars} /> : <p className="text-sm text-slate-500">No data yet.</p>}</CardContent>
        </Card>
      </div>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Sales Dashboard" />
    </div>
  );
}
