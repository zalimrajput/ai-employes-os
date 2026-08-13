"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Bot,
  CalendarClock,
  Cpu,
  MessageSquare,
  Pencil,
  Settings2,
} from "lucide-react";
import Link from "next/link";
import { Avatar } from "@/components/ui/avatar";
import { Badge, StatusDot } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchAIEmployees, fetchTasks } from "@/services/data";
import { formatCompact, timeAgo } from "@/lib/utils";
import { motion } from "framer-motion";

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({ queryKey: ["ai-employees"], queryFn: fetchAIEmployees });
  const { data: tasks } = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });

  const employees = data?.source === "db" ? data.items : [];
  const employee = employees.find((e) => e.id === id);
  const taskItems = tasks?.source === "db" ? tasks.items : [];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-40 w-full" />
        <div className="grid gap-6 lg:grid-cols-3"><Skeleton className="h-80 lg:col-span-1" /><Skeleton className="h-80 lg:col-span-2" /></div>
      </div>
    );
  }

  if (!employee) {
    return (
      <div className="rounded-2xl border border-danger/30 bg-danger/10 p-10 text-center">
        <p className="font-bold text-danger">Employee not found</p>
        <Link href="/dashboard/employees" className="mt-2 inline-block text-sm text-primary-soft hover:underline">← Back to employees</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link href="/dashboard/employees" className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-400 hover:text-white transition-colors">
        <ArrowLeft className="h-4 w-4" /> Back to employees
      </Link>

      {/* Profile header */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="gradient-border rounded-2xl p-[1px]">
        <div className="relative overflow-hidden rounded-2xl bg-card p-6 md:p-8">
          <div className="absolute inset-0 bg-grid opacity-60" />
          <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-5">
              <Avatar name={employee.name} size="xl" />
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold tracking-tight text-white">{employee.name}</h1>
                  <Badge variant={employee.active === false ? "secondary" : "success"}>
                    <StatusDot color={employee.active === false ? "#64748b" : "#22c55e"} />
                    {employee.active === false ? "Offline" : "Online"}
                  </Badge>
                </div>
                <p className="mt-1 text-sm font-semibold text-primary-soft">{employee.role}</p>
                <p className="mt-2 max-w-xl text-sm text-slate-400">{employee.description ?? "No description."}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary"><Pencil className="h-4 w-4" /> Edit</Button>
              <Link href={`/dashboard/chat?employee=${employee.id}`}><Button><MessageSquare className="h-4 w-4" /> Chat</Button></Link>
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left — details */}
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Settings2 className="h-4 w-4 text-primary-soft" /> Configuration</CardTitle></CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-slate-400"><Cpu className="h-4 w-4" /> Model</span>
                <Badge variant="accent">{employee.model ?? "gpt-5"}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-slate-400"><Bot className="h-4 w-4" /> Tools</span>
                <span className="font-semibold text-white">{Object.keys(employee.tools ?? {}).length || 4} enabled</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-slate-400"><CalendarClock className="h-4 w-4" /> Joined</span>
                <span className="text-slate-300">{timeAgo(employee.created_at)}</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right — tasks + timeline */}
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Assigned tasks</CardTitle>
              <CardDescription>{formatCompact(taskItems.length)} active tasks in the workspace</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {taskItems.slice(0, 5).map((t) => (
                <div key={t.id} className="flex items-center gap-3 rounded-xl border border-border-soft bg-card-soft/40 p-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-100">{t.title}</p>
                    <p className="text-xs text-slate-500">{t.status?.replace("_", " ")} · {t.priority}</p>
                  </div>
                  <Badge variant={t.status === "done" ? "success" : t.status === "in_progress" ? "accent" : "secondary"}>{t.status}</Badge>
                </div>
              ))}
              {taskItems.length === 0 && <p className="py-6 text-center text-sm text-slate-500">No tasks yet.</p>}
            </CardContent>
          </Card>

        </div>
      </div>
    </div>
  );
}
