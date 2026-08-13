"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Crown, FileText, ListChecks, Users } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { api } from "@/lib/api/client";
import { formatCompact } from "@/lib/utils";

export default function ExecutiveDashboardPage() {
  const { data: summary } = useQuery({
    queryKey: ["analytics-summary"],
    queryFn: () => api.fetchAnalyticsSummary(),
  });

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Executive overview"
        title="CEO / Executive Dashboard"
        description="The company at a glance — customers, invoices, tasks, and headcount, live from your workspace."
        icon={Crown}
        gradient="from-accent to-primary"
        actions={
          <Link href="/dashboard/chat?agent=executive" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI Executive <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Customers" value={formatCompact(summary?.customers ?? 0)} icon={<Building2 className="h-5 w-5" />} gradient="from-primary to-secondary" loading={!summary} />
        <StatCard label="Invoices" value={formatCompact(summary?.invoices ?? 0)} icon={<FileText className="h-5 w-5" />} gradient="from-secondary to-accent" loading={!summary} />
        <StatCard label="Tasks" value={formatCompact(summary?.tasks ?? 0)} icon={<ListChecks className="h-5 w-5" />} gradient="from-accent to-success" loading={!summary} />
        <StatCard label="Employees" value={formatCompact(summary?.employees ?? 0)} icon={<Users className="h-5 w-5" />} gradient="from-success to-accent" loading={!summary} />
      </div>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="CEO / Executive Dashboard" />
    </div>
  );
}
