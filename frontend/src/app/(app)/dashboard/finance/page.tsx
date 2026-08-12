"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, DollarSign, FileText, Landmark, Wallet, Receipt } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { RevenueChart } from "@/components/dashboard/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";
import { currency, fetchInvoices } from "@/services/business";

const BUDGETS = [
  { name: "Payroll", spent: 41200, total: 46000, color: "from-primary to-secondary" },
  { name: "Marketing", spent: 14800, total: 20000, color: "from-secondary to-accent" },
  { name: "Operations", spent: 8900, total: 12000, color: "from-accent to-success" },
  { name: "Software", spent: 4300, total: 5000, color: "from-warning to-danger" },
];

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "secondary"> = {
  paid: "success",
  pending: "warning",
  overdue: "danger",
  draft: "secondary",
};

export default function FinanceDashboardPage() {
  const { data: invoicesData, isLoading } = useQuery({
    queryKey: ["invoices"],
    queryFn: fetchInvoices,
  });

  const invoices =
    invoicesData?.source === "db" || invoicesData?.source === "demo"
      ? invoicesData.items
      : [];

  const totalInvoiced = invoices.reduce((acc, i) => acc + Number(i.amount ?? 0), 0);
  const outstanding = invoices
    .filter((i) => (i.status ?? "").toLowerCase() !== "paid")
    .reduce((acc, i) => acc + Number(i.amount ?? 0), 0);

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Financial control"
        title="Finance Dashboard"
        description="Cash flow, budgets, expenses, and receivables — everything accounting needs."
        icon={Landmark}
        gradient="from-success to-primary"
        actions={
          <Link href="/dashboard/chat?agent=finance" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI Finance <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Invoiced" value={currency(totalInvoiced)} delta={11} icon={<Wallet className="h-5 w-5" />} gradient="from-primary to-secondary" loading={isLoading} />
        <StatCard label="Outstanding AR" value={currency(outstanding)} delta={7} icon={<FileText className="h-5 w-5" />} gradient="from-warning to-danger" loading={isLoading} />
        <StatCard label="Invoices" value={String(invoices.length)} delta={14} icon={<DollarSign className="h-5 w-5" />} gradient="from-secondary to-accent" loading={isLoading} />
        <StatCard label="Expenses (MTD)" value="$69.2k" delta={-4} icon={<Receipt className="h-5 w-5" />} gradient="from-accent to-warning" loading={false} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Cash flow</CardTitle>
            <CardDescription>Monthly income vs expenses</CardDescription>
          </CardHeader>
          <CardContent><RevenueChart /></CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Budget utilization</CardTitle>
            <CardDescription>Spend vs allocation by category</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {BUDGETS.map((b) => {
              const pct = Math.round((b.spent / b.total) * 100);
              return (
                <div key={b.name}>
                  <div className="mb-1.5 flex items-center justify-between text-sm">
                    <span className="font-semibold text-slate-200">{b.name}</span>
                    <span className="text-xs text-slate-400">${b.spent.toLocaleString()} / ${b.total.toLocaleString()}</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-card-soft">
                    <div className={`h-full rounded-full bg-gradient-to-r ${b.color}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      {/* Invoices — live from the backend */}
      <Card>
        <CardHeader>
          <CardTitle>Recent invoices</CardTitle>
          <CardDescription>Receivables and payment status</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {isLoading ? (
            <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
          ) : invoices.length === 0 ? (
            <p className="text-sm text-slate-500">No invoices yet — create one to see it here.</p>
          ) : (
            invoices.slice(0, 8).map((inv, i) => {
              const status = (inv.status ?? "draft").toLowerCase();
              return (
                <motion.div
                  key={inv.id}
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  whileHover={{ x: 4 }}
                  className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-card-soft text-sm font-bold text-primary-soft">
                    {(inv.invoice_number ?? inv.id.slice(0, 4)).replace("#", "").slice(-4)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{inv.invoice_number ?? "Invoice"}</p>
                    <p className="text-xs text-slate-500">
                      {inv.due_date ? `Due ${inv.due_date}` : inv.created_at ? `Created ${inv.created_at.slice(0, 10)}` : "No due date"}
                    </p>
                  </div>
                  <span className="text-sm font-bold text-white">{currency(inv.amount)}</span>
                  <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>
                    {inv.status ?? "draft"}
                  </Badge>
                </motion.div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Top-line movements</CardTitle>
          <CardDescription>Largest inflows and outflows this month</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            { label: "Total invoiced (MTD)", amount: `+${currency(totalInvoiced)}`, up: true },
            { label: "Outstanding receivables", amount: `+${currency(outstanding)}`, up: true },
          ].map((m, i) => (
            <div key={i} className="flex items-center justify-between rounded-xl border border-border-soft bg-card-soft/40 p-3.5">
              <p className="text-sm font-medium text-slate-200">{m.label}</p>
              <span className="inline-flex items-center gap-1 text-sm font-bold text-green-400">
                <ArrowUpRight className="h-4 w-4" />
                {m.amount}
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Finance Dashboard" />
    </div>
  );
}
