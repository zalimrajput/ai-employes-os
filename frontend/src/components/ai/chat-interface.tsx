"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Bot, ImagePlus, Paperclip, Send, Sparkles, X } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { AIMessage, ImagePart } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { useSession } from "@/hooks/use-session";
import { api } from "@/lib/api/client";
import { toast } from "sonner";

function TypingDots() {
  return (
    <div className="flex items-center gap-1.5 py-2">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 animate-typing rounded-full bg-primary-soft"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

/** Lightweight markdown-ish rendering for assistant replies. */
function MessageBody({ text }: { text: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {text.split("\n").map((line, i) => {
        if (line.startsWith("**") && line.endsWith("**")) {
          return <p key={i} className="font-bold text-white">{line.replace(/\*\*/g, "")}</p>;
        }
        if (line.startsWith("- ") || line.startsWith("• ")) {
          return (
            <p key={i} className="flex gap-2 text-slate-200">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gradient-to-r from-primary to-accent" />
              <span>{line.slice(2)}</span>
            </p>
          );
        }
        if (!line.trim()) return <div key={i} className="h-2" />;
        return <p key={i} className="text-slate-200">{line}</p>;
      })}
    </div>
  );
}

/**
 * Demo-only canned replies. Real conversations (non `demo-` ids) go through the
 * backend AI engine; these exist solely so the pre-seeded demo rows in a fresh
 * workspace still feel interactive.
 */
type Attachment = { id: string; name: string; mime: string; url: string };
type LocalMessage = AIMessage & { attachments?: string[] };

const DEMO_REPLIES = [
  "Done! I've drafted it and queued it for review. Want me to send it now?",
  "I found 3 related records in the CRM. Here's what I prepared — approve and I'll execute.",
  "Completed ✅ — updated the pipeline and scheduled the follow-up for Friday at 3 PM.",
  "Here's the summary you asked for. I also extracted 5 action items and created tasks for each.",
  "On it. I'll track this conversation and remind you if there's no reply within 3 days.",
];

export function ChatInterface({
  employeeName,
  conversationId,
  initialMessages,
}: {
  employeeName: string;
  conversationId: string;
  initialMessages: AIMessage[];
}) {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<LocalMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  function handleFiles(files: FileList | null) {
    if (!files) return;
    for (const file of Array.from(files)) {
      if (!["image/png", "image/jpeg", "image/webp", "image/gif"].includes(file.type)) {
        toast.error(`Skipped ${file.name} — only PNG, JPEG, WebP or GIF images are supported`);
        continue;
      }
      if (file.size > 5 * 1024 * 1024) {
        toast.error(`Skipped ${file.name} — images must be 5 MB or smaller`);
        continue;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const url = String(reader.result ?? "");
        if (!url) return;
        setAttachments((prev) =>
          prev.length >= 4 ? prev : [...prev, { id: `${Date.now()}-${Math.random()}`, name: file.name, mime: file.type, url }]
        );
      };
      reader.readAsDataURL(file);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if ((!text && attachments.length === 0) || thinking) return;
    const images: ImagePart[] = attachments.map((a) => ({
      type: "image_url",
      image_url: { url: a.url },
    }));
    const localAttachments = attachments.map((a) => a.url);
    setInput("");
    setAttachments([]);
    setThinking(true);

    const userMsg: LocalMessage = {
      id: `local-${Date.now()}`,
      conversation_id: conversationId,
      role: "user",
      message: text || "Describe the attached image(s).",
      attachments: localAttachments,
    };
    setMessages((m) => [...m, userMsg]);

    const isDemo =
      conversationId.startsWith("demo-") &&
      process.env.NEXT_PUBLIC_ENABLE_DEMO === "true";

    let reply: string;
    if (isDemo) {
      // Demo rows are UI-only — keep them responsive without a backend.
      reply = DEMO_REPLIES[Math.floor(Math.random() * DEMO_REPLIES.length)];
    } else {
      try {
        // Real conversation: run the AI agent through the backend, which also
        // persists the user message + assistant reply.
        const result = await api.sendAIMessage({
          conversation_id: conversationId,
          message: text,
          images,
        });
        reply =
          (result?.message ?? "").trim() ||
          "I couldn't generate a response — please try again.";
      } catch (err) {
        reply = `⚠️ ${(err as Error).message ?? "Something went wrong."}`;
      }
    }

    const streamed: AIMessage = {
      id: `local-${Date.now() + 1}`,
      conversation_id: conversationId,
      role: "assistant",
      message: "",
    };
    setMessages((m) => [...m, streamed]);

    const chars = reply.split("");
    for (let i = 0; i < chars.length; i++) {
      await new Promise((r) => setTimeout(r, 14));
      setMessages((m) =>
        m.map((msg) => (msg.id === streamed.id ? { ...msg, message: reply.slice(0, i + 1) } : msg))
      );
    }
    setThinking(false);
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto p-4 md:p-6 no-scrollbar">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className={cn("flex gap-3", isUser && "flex-row-reverse")}
            >
              {isUser ? (
                <Avatar name={session?.user?.name ?? session?.user?.email} size="sm" className="shrink-0" />
              ) : (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-secondary">
                  <Bot className="h-4 w-4 text-white" />
                </div>
              )}
              <div
                className={cn(
                  "max-w-[78%] rounded-2xl border px-4 py-3 shadow-lg",
                  isUser
                    ? "border-transparent bg-gradient-to-r from-primary to-secondary text-white"
                    : "border-border-soft bg-card-soft/70"
                )}
              >
                {!isUser && (
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-primary-soft">
                    <Sparkles className="h-3 w-3" /> {employeeName}
                  </p>
                )}
                {msg.attachments && msg.attachments.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-2">
                    {msg.attachments.map((src, i) => (
                      <img
                        key={i}
                        src={src}
                        alt={`attachment ${i + 1}`}
                        className="h-24 w-24 rounded-lg border border-white/20 object-cover"
                      />
                    ))}
                  </div>
                )}
                {msg.message ? <MessageBody text={msg.message} /> : <TypingDots />}
              </div>
            </motion.div>
          );
        })}
      </div>

      <div className="border-t border-border-soft bg-card/40 p-3 md:p-4">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          multiple
          hidden
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
        {attachments.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {attachments.map((a) => (
              <div key={a.id} className="group relative">
                <img
                  src={a.url}
                  alt={a.name}
                  className="h-14 w-14 rounded-lg border border-border-soft object-cover"
                />
                <button
                  type="button"
                  onClick={() => setAttachments((prev) => prev.filter((x) => x.id !== a.id))}
                  className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-danger text-white shadow"
                  aria-label={`Remove ${a.name}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="relative">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={`Message ${employeeName}…`}
            className="min-h-[56px] max-h-36 resize-none pr-24 py-3.5"
          />
          <div className="absolute bottom-2.5 right-2.5 flex items-center gap-1.5">
            <Button
              variant="ghost"
              size="iconSm"
              aria-label="Attach images"
              onClick={() => fileInputRef.current?.click()}
              disabled={attachments.length >= 4}
            >
              {attachments.length >= 4 ? (
                <ImagePlus className="h-4 w-4 opacity-40" />
              ) : (
                <Paperclip className="h-4 w-4" />
              )}
            </Button>
            <Button
              size="iconSm"
              onClick={handleSend}
              disabled={(!input.trim() && attachments.length === 0) || thinking}
              aria-label="Send"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <p className="mt-2 text-center text-[11px] text-slate-600">
          AI Employee OS can make mistakes. Review important actions before they execute.
        </p>
      </div>
    </div>
  );
}
