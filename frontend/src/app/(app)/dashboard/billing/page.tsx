"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Check, Crown, Rocket, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { fetchPlans } from "@/services/business";

const ICONS = [Zap, Rocket, Crown];

function formatCount(n: number | null | undefined): string {
  if (n == null) return "Unlimited";
  if (n >= 1000) return `${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k`;
  return String(n);
}

export default function BillingPage() {
  const { data, isLoading } = useQuery({ queryKey: ["plans"], queryFn: fetchPlans });
  const plans = data?.source === "db" ? data.items : [];
  const [selected, setSelected] = useState<string | null>(null);

  const activePlans = plans.filter((p) => p.active !== false);
  const highlightIndex = activePlans.length > 2 ? 1 : -1;

  return (
    <div className="space-y-8">
      <div className="text-center">
        <p className="text-sm font-semibold text-primary-soft">Simple, transparent pricing</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-white">Billing & Plans</h1>
        <p className="mx-auto mt-2 max-w-xl text-sm text-slate-400">
          One subscription replaces a dozen software tools and an entire admin team.
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-96" />)}
        </div>
      ) : activePlans.length === 0 ? (
        <p className="text-center text-sm text-slate-500">No plans published yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {activePlans.map((plan, i) => {
            const Icon = ICONS[i % ICONS.length];
            const highlight = i === highlightIndex;
            const isSelected = selected === plan.id;
            const features = [
              plan.max_users != null ? `Up to ${plan.max_users} user${plan.max_users === 1 ? "" : "s"}` : "Unlimited users",
              `${formatCount(plan.ai_requests_limit)} AI requests/mo`,
              `${plan.storage_limit_gb ?? 0} GB storage`,
            ];
            return (
              <motion.div
                key={plan.id}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                whileHover={{ y: -8 }}
                onClick={() => setSelected(plan.id)}
                className={cn(
                  "cursor-pointer rounded-2xl p-[1px] transition-all",
                  highlight ? "gradient-border" : "border border-border-soft"
                )}
              >
                <div className={cn("relative rounded-2xl bg-card p-6 h-full", isSelected && "ring-2 ring-primary/50")}>
                  {highlight && (
                    <Badge variant="default" className="absolute -top-3 left-1/2 -translate-x-1/2">Most popular</Badge>
                  )}
                  <div className="flex items-center gap-2.5">
                    <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", highlight ? "bg-gradient-to-br from-primary to-secondary" : "bg-card-soft")}>
                      <Icon className={cn("h-5 w-5", highlight ? "text-white" : "text-primary-soft")} />
                    </div>
                    <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                  </div>
                  <p className="mt-2 text-sm text-slate-400">{plan.description ?? "—"}</p>
                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-4xl font-bold tracking-tight text-white">
                      ${plan.price_monthly ?? 0}
                    </span>
                    <span className="text-sm text-slate-500">/month</span>
                  </div>
                  <ul className="mt-6 space-y-2.5">
                    {features.map((f) => (
                      <li key={f} className="flex items-center gap-2 text-sm text-slate-300">
                        <Check className="h-4 w-4 shrink-0 text-success" /> {f}
                      </li>
                    ))}
                  </ul>
                  <Button
                    variant={highlight ? "default" : "secondary"}
                    className="mt-6 w-full"
                    onClick={() => toast.info(`${plan.name} plan selected — checkout opens with Stripe.`)}
                  >
                    {isSelected ? "Current plan" : `Choose ${plan.name}`}
                  </Button>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
