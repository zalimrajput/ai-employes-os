"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, Cpu, ListChecks, Workflow } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { fetchOrgStats } from "@/services/data";
import { formatCompact } from "@/lib/utils";

export default function AnalyticsPage() {
  const { data: stats } = useQuery({ queryKey: ["org-stats"], queryFn: fetchOrgStats });

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm font-semibold text-primary-soft">Performance intelligence</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-white md:text-3xl">Analytics</h1>
        <p className="mt-1 text-sm text-slate-400">Live counts of how much work your AI workforce absorbs.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="AI Requests" value={formatCompact(stats?.messages ?? 0)} icon={<Cpu className="h-5 w-5" />} gradient="from-primary to-secondary" loading={!stats} />
        <StatCard label="Active Employees" value={formatCompact(stats?.activeEmployees ?? 0)} icon={<Bot className="h-5 w-5" />} gradient="from-accent to-primary" loading={!stats} />
        <StatCard label="Tasks" value={formatCompact(stats?.tasks ?? 0)} icon={<ListChecks className="h-5 w-5" />} gradient="from-secondary to-accent" loading={!stats} />
        <StatCard label="Workflows" value={formatCompact(stats?.workflows ?? 0)} icon={<Workflow className="h-5 w-5" />} gradient="from-success to-accent" loading={!stats} />
      </div>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Reports & Analytics Dashboard" />
    </div>
  );
}
