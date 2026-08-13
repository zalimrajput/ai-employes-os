"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Loader2, Plus, Sparkles } from "lucide-react";
import { KanbanBoard } from "@/components/tasks/kanban";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { createTask, fetchTasks, updateTaskStatus } from "@/services/data";
import type { TaskStatus } from "@/lib/api/types";
import { toast } from "sonner";
import { motion } from "framer-motion";

export default function TasksPage() {
  const { data, isLoading } = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState<"low" | "medium" | "high" | "urgent">("medium");

  const tasks = data?.source === "db" ? data.items : [];

  const moveMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) => updateTaskStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Task moved");
    },
    onError: () => toast.error("Could not update task"),
  });

  const createMutation = useMutation({
    mutationFn: () => createTask({ title, priority }),
    onSuccess: (result) => {
      if (result.error) {
        toast.error(result.error);
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Task created");
      setTitle("");
      setShowForm(false);
    },
    onError: () => toast.error("Could not create task"),
  });

  function handleCreate() {
    if (!title.trim()) return;
    createMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary-soft">Work orchestration</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-white md:text-3xl">
            Task Board
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Drag cards to move work through the pipeline — AI creates, humans approve.
          </p>
        </div>
        <Button onClick={() => setShowForm((s) => !s)}>
          {showForm ? <Loader2 className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showForm ? "Close" : "New Task"}
        </Button>
      </div>

      {showForm && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-primary/30 bg-card p-5">
          <div className="grid gap-4 sm:grid-cols-[1fr_auto_auto]">
            <div className="space-y-2">
              <Label>Task title</Label>
              <Input placeholder="e.g. Send quotation to Acme Corp" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Priority</Label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as typeof priority)}
                className="h-11 w-full rounded-xl border border-border-soft bg-card-soft/60 px-3 text-sm text-white focus:border-primary/60 focus:outline-none"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
            <div className="flex items-end">
              <Button onClick={handleCreate} className="w-full sm:w-auto">
                <Sparkles className="h-4 w-4" /> Create
              </Button>
            </div>
          </div>
        </motion.div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-96" />)}
        </div>
      ) : (
        <KanbanBoard tasks={tasks} onMove={(id, status) => moveMutation.mutate({ id, status })} />
      )}
    </div>
  );
}
