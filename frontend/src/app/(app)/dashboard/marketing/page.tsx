"use client";

import { ArrowRight, BarChart3, Megaphone, PenLine, Share2, Target, Users } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { UsageBars, TasksChart } from "@/components/dashboard/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Avatar } from "@/components/ui/avatar";
import { motion } from "framer-motion";

const CAMPAIGNS = [
  { name: "Q3 Product Launch", channel: "Email", reach: "48k", conv: 4.2, status: "Live", avatar: "QL" },
  { name: "SaaS Weekly Digest", channel: "Newsletter", reach: "22k", conv: 3.1, status: "Live", avatar: "SW" },
  { name: "LinkedIn DTC Push", channel: "Social", reach: "64k", conv: 1.8, status: "Scheduled", avatar: "LD" },
  { name: "YouTube Explainer", channel: "Video", reach: "31k", conv: 2.9, status: "Draft", avatar: "YT" },
];

const CHANNELS = [
  { name: "Email", value: 320 },
  { name: "Social", value: 260 },
  { name: "Search", value: 180 },
  { name: "Content", value: 120 },
];

export default function MarketingDashboardPage() {
  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Growth engine"
        title="Marketing Dashboard"
        description="Campaign performance, audience growth, content output, and channel ROI."
        icon={Megaphone}
        gradient="from-secondary to-danger"
        actions={
          <Link href="/dashboard/chat?agent=marketing" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI Marketing <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Campaigns Live" value="12" delta={4} icon={<Megaphone className="h-5 w-5" />} gradient="from-primary to-secondary" loading={false} />
        <StatCard label="Audience Growth" value="+8.2k" delta={18} icon={<Users className="h-5 w-5" />} gradient="from-secondary to-accent" loading={false} />
        <StatCard label="Open Rate" value="42%" delta={6} icon={<Target className="h-5 w-5" />} gradient="from-accent to-success" loading={false} />
        <StatCard label="Content Pieces" value="96" delta={11} icon={<PenLine className="h-5 w-5" />} gradient="from-warning to-danger" loading={false} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Active campaigns</CardTitle>
            <CardDescription>Reach and conversion by campaign</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {CAMPAIGNS.map((c, i) => (
              <motion.div
                key={c.name}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                whileHover={{ x: 4 }}
                className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
              >
                <div className="flex items-center gap-3">
                  <Avatar name={c.avatar} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{c.name}</p>
                    <p className="text-xs text-slate-500">{c.channel} · {c.reach} reached</p>
                  </div>
                  <Badge variant={c.status === "Live" ? "success" : c.status === "Scheduled" ? "accent" : "secondary"}>{c.status}</Badge>
                </div>
                <div className="mt-2.5 flex items-center gap-3">
                  <Progress value={c.conv * 15} className="flex-1" />
                  <span className="text-xs font-bold text-white">{c.conv}% conv.</span>
                </div>
              </motion.div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Channel performance</CardTitle>
              <CardDescription>Leads generated per channel</CardDescription>
            </CardHeader>
            <CardContent><UsageBars data={CHANNELS} /></CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Content velocity</CardTitle>
              <CardDescription>Pieces published this week</CardDescription>
            </CardHeader>
            <CardContent><TasksChart /></CardContent>
          </Card>
        </div>
      </div>

      {/* AI content */}
      <Card>
        <CardHeader>
          <CardTitle>AI content pipeline</CardTitle>
          <CardDescription>Drafts generated by your AI Content Writer</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {[
              { icon: "📣", title: "Product launch email", body: "Draft ready for the Q3 launch — 2 A/B variants suggested." },
              { icon: "✍️", title: "Blog: 'AI in Sales'", body: "1,200 words drafted from your knowledge base. Needs final edit." },
              { icon: "🖼️", title: "LinkedIn carousel", body: "5-slide concept generated from the case study deck." },
            ].map((c) => (
              <div key={c.title} className="rounded-xl border border-border-soft bg-card-soft/40 p-4 transition-colors hover:border-accent/30">
                <span className="text-xl">{c.icon}</span>
                <p className="mt-2 text-sm font-bold text-white">{c.title}</p>
                <p className="mt-1 text-xs text-slate-400">{c.body}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 inline-flex items-center gap-2 text-xs text-slate-500">
            <BarChart3 className="h-3.5 w-3.5" /> Powered by your AI Content Writer · <Share2 className="h-3.5 w-3.5" /> ready to publish
          </p>
        </CardContent>
      </Card>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Marketing Dashboard" />
    </div>
  );
}
