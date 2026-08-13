"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Megaphone, PenLine, Target, Users } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { currency, fetchCampaigns } from "@/services/business";
import { motion } from "framer-motion";

const STATUS_VARIANT: Record<string, "success" | "accent" | "secondary" | "default"> = {
  live: "success",
  active: "success",
  scheduled: "accent",
  draft: "secondary",
  completed: "default",
};

export default function MarketingDashboardPage() {
  const { data, isLoading } = useQuery({ queryKey: ["campaigns"], queryFn: fetchCampaigns });

  const campaigns = data?.source === "db" ? data.items : [];
  const liveCampaigns = campaigns.filter((c) => (c.status ?? "").toLowerCase() === "live").length;

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Growth engine"
        title="Marketing Dashboard"
        description="Campaign performance and content output tracked in your marketing module."
        icon={Megaphone}
        gradient="from-secondary to-danger"
        actions={
          <Link href="/dashboard/chat?agent=marketing" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI Marketing <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Campaigns" value={String(campaigns.length)} icon={<Megaphone className="h-5 w-5" />} gradient="from-primary to-secondary" loading={isLoading} />
        <StatCard label="Live Campaigns" value={String(liveCampaigns)} icon={<Target className="h-5 w-5" />} gradient="from-secondary to-accent" loading={isLoading} />
        <StatCard label="Campaign Budget" value={currency(campaigns.reduce((acc, c) => acc + Number(c.budget ?? 0), 0))} icon={<Users className="h-5 w-5" />} gradient="from-accent to-success" loading={isLoading} />
      </div>

      {/* Campaigns — live from the backend */}
      <Card>
        <CardHeader>
          <CardTitle>Campaigns</CardTitle>
          <CardDescription>Campaigns in your marketing module</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
          ) : campaigns.length === 0 ? (
            <p className="text-sm text-slate-500">No campaigns yet — create one to see it here.</p>
          ) : (
            campaigns.slice(0, 8).map((c, i) => {
              const status = (c.status ?? "draft").toLowerCase();
              return (
                <motion.div
                  key={c.id}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  whileHover={{ x: 4 }}
                  className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-secondary to-accent">
                      <PenLine className="h-4.5 w-4.5 text-white" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold text-white">{c.name}</p>
                      <p className="text-xs text-slate-500">
                        {c.campaign_type ?? "Campaign"}
                        {c.budget != null ? ` · ${currency(c.budget)} budget` : ""}
                        {c.start_date ? ` · starts ${c.start_date}` : ""}
                      </p>
                    </div>
                    <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>{c.status ?? "draft"}</Badge>
                  </div>
                </motion.div>
              );
            })
          )}
        </CardContent>
      </Card>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Marketing Dashboard" />
    </div>
  );
}
