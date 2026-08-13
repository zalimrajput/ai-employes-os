"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Headset, Mail, MessageCircle } from "lucide-react";
import Link from "next/link";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { ModuleWidgets } from "@/components/dashboard/module-widgets";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { timeAgo } from "@/lib/utils";
import { fetchEmailThreads, fetchWhatsappMessages } from "@/services/business";
import { motion } from "framer-motion";

export default function SupportDashboardPage() {
  const { data: threadsData, isLoading: threadsLoading } = useQuery({ queryKey: ["email-threads"], queryFn: fetchEmailThreads });
  const { data: whatsappData, isLoading: whatsappLoading } = useQuery({ queryKey: ["whatsapp-messages"], queryFn: fetchWhatsappMessages });

  const threads = threadsData?.source === "db" ? threadsData.items : [];
  const whatsappMessages = whatsappData?.source === "db" ? whatsappData.items : [];

  return (
    <div className="space-y-8">
      <DashboardHeader
        eyebrow="Customer care"
        title="Customer Support Dashboard"
        description="Email threads and WhatsApp activity handled by your support team."
        icon={Headset}
        gradient="from-accent to-success"
        actions={
          <Link href="/dashboard/chat?agent=support" className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40">
            Ask AI Support <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Email Threads" value={String(threads.length)} icon={<Mail className="h-5 w-5" />} gradient="from-primary to-secondary" loading={threadsLoading} />
        <StatCard label="WhatsApp Messages" value={String(whatsappMessages.length)} icon={<MessageCircle className="h-5 w-5" />} gradient="from-secondary to-accent" loading={whatsappLoading} />
        <StatCard label="AI-Generated Replies" value={String(whatsappMessages.filter((m) => m.ai_generated).length)} icon={<Headset className="h-5 w-5" />} gradient="from-accent to-success" loading={whatsappLoading} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Email queue — live from the backend */}
        <Card>
          <CardHeader>
            <CardTitle>Email threads</CardTitle>
            <CardDescription>Latest customer conversations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {threadsLoading ? (
              <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
            ) : threads.length === 0 ? (
              <p className="text-sm text-slate-500">No email threads yet.</p>
            ) : (
              threads.slice(0, 6).map((t, i) => (
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
                    <Mail className="h-4 w-4 text-primary-soft" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{t.subject ?? "Untitled thread"}</p>
                    <p className="text-xs text-slate-500">
                      {t.category ?? t.ai_priority ?? "inbox"}{t.created_at ? ` · ${timeAgo(t.created_at)}` : ""}
                    </p>
                  </div>
                  <Badge variant={t.ai_priority === "high" ? "danger" : t.ai_priority === "urgent" ? "danger" : "secondary"}>
                    {t.ai_priority ?? "normal"}
                  </Badge>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>

        {/* WhatsApp activity — live from the backend */}
        <Card>
          <CardHeader>
            <CardTitle>WhatsApp activity</CardTitle>
            <CardDescription>Latest messages across your WhatsApp line</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {whatsappLoading ? (
              <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
            ) : whatsappMessages.length === 0 ? (
              <p className="text-sm text-slate-500">No WhatsApp messages yet.</p>
            ) : (
              whatsappMessages.slice(0, 6).map((m, i) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  whileHover={{ x: 4 }}
                  className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-card-soft">
                    <MessageCircle className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{m.message ?? "—"}</p>
                    <p className="text-xs text-slate-500">
                      {m.direction ?? "—"}{m.created_at ? ` · ${timeAgo(m.created_at)}` : ""}
                    </p>
                  </div>
                  <Badge variant={m.direction === "inbound" ? "default" : m.ai_generated ? "accent" : "secondary"}>
                    {m.ai_generated ? "AI" : m.direction ?? "—"}
                  </Badge>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Module widgets — gated by the org's enabled modules */}
      <ModuleWidgets dashboardName="Customer Support Dashboard" />
    </div>
  );
}
