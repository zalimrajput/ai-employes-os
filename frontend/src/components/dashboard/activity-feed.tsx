"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Bot, FileText, Mail, CreditCard, Users, CalendarClock, Workflow } from "lucide-react";
import { fetchActivities } from "@/services/business";
import { timeAgo } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const ICONS: Record<string, React.ReactNode> = {
  email: <Mail className="h-3.5 w-3.5" />,
  invoice: <CreditCard className="h-3.5 w-3.5" />,
  document: <FileText className="h-3.5 w-3.5" />,
  employee: <Users className="h-3.5 w-3.5" />,
  meeting: <CalendarClock className="h-3.5 w-3.5" />,
  workflow: <Workflow className="h-3.5 w-3.5" />,
  customer: <Users className="h-3.5 w-3.5" />,
  lead: <Users className="h-3.5 w-3.5" />,
  quotation: <FileText className="h-3.5 w-3.5" />,
  deal: <CreditCard className="h-3.5 w-3.5" />,
  note: <FileText className="h-3.5 w-3.5" />,
  task: <Workflow className="h-3.5 w-3.5" />,
  reminder: <CalendarClock className="h-3.5 w-3.5" />,
};

const ACCENTS = [
  "text-accent bg-accent/15",
  "text-green-400 bg-success/15",
  "text-violet-400 bg-secondary/15",
  "text-cyan-400 bg-accent/15",
  "text-amber-400 bg-warning/15",
];

export function ActivityFeed() {
  const { data, isLoading } = useQuery({ queryKey: ["activities"], queryFn: fetchActivities });
  const activities = data?.source === "db" ? data.items : [];

  return (
    <div className="space-y-1">
      {isLoading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : activities.length === 0 ? (
        <p className="text-sm text-slate-500">No activity recorded yet.</p>
      ) : (
        activities.slice(0, 6).map((a, i) => (
          <motion.div
            key={a.id}
            initial={{ opacity: 0, x: -12 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.07 }}
            className="flex items-start gap-3 rounded-xl p-3 transition-colors hover:bg-card-soft/60"
          >
            <div className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${ACCENTS[i % ACCENTS.length]}`}>
              {ICONS[(a.entity_type ?? "note").toLowerCase()] ?? <Bot className="h-3.5 w-3.5" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-200">{a.action}</p>
              <p className="text-xs text-slate-500">{timeAgo(a.created_at)}</p>
            </div>
            <Bot className="mt-1 h-3.5 w-3.5 shrink-0 text-slate-600" />
          </motion.div>
        ))
      )}
    </div>
  );
}
