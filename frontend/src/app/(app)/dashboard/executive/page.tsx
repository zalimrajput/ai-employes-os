"use client";

import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Crown,
  DollarSign,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { RevenueChart, EfficiencyChart } from "@/components/dashboard/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusDot } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { motion } from "framer-motion";

const KPIS = [
  { name: "Monthly revenue", value: "$112.4k", change: "+14%", up: true },
  { name: "Active customers", value: "1,284", change: "+8%", up: true },
  { name: "Gross margin", value: "71%", change: "+3%", up: true },
  { name: "Churn rate", value: "2.1%", change: "-0.4%", up: true },
];

const INITIATIVES = [
  { name: "Q3 revenue target", value: 74, owner: "Alex Morgan", status: "On track", color: "from-success to-accent" },
  { name: "Enterprise expansion", value: 52, owner: "Priya Sharma", status: "In progress", color: "from-primary to-secondary" },
  { name: "AI workforce rollout", value: 88, owner: "Jamie Lee", status: "Near complete", color: "from-accent to-primary" },
  { name: "Cost optimization", value: 41, owner: "Sam Rivera", status: "In progress", color: "from-warning to-danger" },
];

export default function ExecutiveDashboardPage() {
  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Executive overview"
        title="CEO / Executive Dashboard"
        description="The company at a glance — revenue, growth, headcount, and the health of every department."
        icon={Crown}
        gradient="from-accent to-primary"
        actions={
          <Link href="/dashboard/chat?agent=executive" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI Executive <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Revenue (MTD)" value="$112.4k" delta={14} icon={<DollarSign className="h-5 w-5" />} gradient="from-primary to-secondary" loading={false} />
        <StatCard label="New Customers" value="86" delta={21} icon={<Target className="h-5 w-5" />} gradient="from-secondary to-accent" loading={false} />
        <StatCard label="Headcount" value="48" delta={5} icon={<Users className="h-5 w-5" />} gradient="from-accent to-success" loading={false} />
        <StatCard label="Runway" value="24 mo" delta={3} icon={<TrendingUp className="h-5 w-5" />} gradient="from-success to-accent" loading={false} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Revenue growth</CardTitle>
            <CardDescription>Consolidated monthly revenue with AI-handled share</CardDescription>
          </CardHeader>
          <CardContent><RevenueChart /></CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Automation efficiency</CardTitle>
            <CardDescription>Share of work handled by the AI workforce</CardDescription>
          </CardHeader>
          <CardContent><EfficiencyChart /></CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Key performance indicators */}
        <Card>
          <CardHeader>
            <CardTitle>Company KPIs</CardTitle>
            <CardDescription>Snapshot vs last quarter</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            {KPIS.map((k) => (
              <div key={k.name} className="rounded-xl border border-border-soft bg-card-soft/40 p-4">
                <p className="text-xs text-slate-500">{k.name}</p>
                <p className="mt-1 text-xl font-bold text-white">{k.value}</p>
                <p className={`mt-1 inline-flex items-center gap-1 text-xs font-semibold ${k.up ? "text-green-400" : "text-red-400"}`}>
                  <ArrowUpRight className="h-3 w-3" /> {k.change}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Strategic initiatives */}
        <Card>
          <CardHeader>
            <CardTitle>Strategic initiatives</CardTitle>
            <CardDescription>Progress toward company goals</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {INITIATIVES.map((i) => (
              <div key={i.name}>
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="font-semibold text-slate-200">{i.name}</span>
                  <span className="flex items-center gap-2 text-xs text-slate-500">
                    <StatusDot color={i.status === "On track" ? "#22c55e" : i.status === "Near complete" ? "#06b6d4" : "#f59e0b"} />
                    {i.status}
                  </span>
                </div>
                <Progress value={i.value} barClassName={i.color} />
                <p className="mt-1 text-xs text-slate-500">{i.value}% · owner: {i.owner}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Department pulse */}
      <Card>
        <CardHeader>
          <CardTitle>Department pulse</CardTitle>
          <CardDescription>Activity and health across the org</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { dept: "Sales", value: "92", icon: TrendingUp, color: "text-green-400" },
              { dept: "Finance", value: "87", icon: Activity, color: "text-cyan-400" },
              { dept: "Operations", value: "79", icon: Target, color: "text-amber-400" },
              { dept: "Support", value: "94", icon: Users, color: "text-violet-400" },
            ].map((d, i) => (
              <motion.div
                key={d.dept}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                whileHover={{ y: -4 }}
                className="rounded-xl border border-border-soft bg-card-soft/40 p-4"
              >
                <div className="flex items-center justify-between">
                  <d.icon className={`h-5 w-5 ${d.color}`} />
                  <span className="text-lg font-bold text-white">{d.value}</span>
                </div>
                <p className="mt-2 text-sm font-semibold text-slate-200">{d.dept}</p>
                <Progress value={Number(d.value)} className="mt-2" />
              </motion.div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="CEO / Executive Dashboard" />
    </div>
  );
}
