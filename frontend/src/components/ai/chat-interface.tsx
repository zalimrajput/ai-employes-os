"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Bot,
  Check,
  Copy,
  Download,
  ImagePlus,
  MessageSquarePlus,
  Paperclip,
  Send,
  Sparkles,
  X,
} from "lucide-react";
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
    <div className="flex items-center gap-1.5 py-1.5">
      <span className="flex h-5 w-5 items-center justify-center">
        <span className="h-2 w-2 animate-typing rounded-full bg-gradient-to-r from-primary to-accent" style={{ animationDelay: "0s" }} />
      </span>
      <span className="h-2 w-2 animate-typing rounded-full bg-primary-soft" style={{ animationDelay: "0.15s" }} />
      <span className="h-2 w-2 animate-typing rounded-full bg-primary-soft" style={{ animationDelay: "0.3s" }} />
    </div>
  );
}

/** Code block with a 1-click copy button. */
function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
      toast.success("Code copied to clipboard");
    } catch {
      toast.error("Could not access the clipboard");
    }
  }
  return (
    <div className="group/code my-2 overflow-hidden rounded-xl border border-border-soft bg-[#0b1220] shadow-inner">
      <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.04] px-3 py-1.5">
        <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {language || "code"}
        </span>
        <button
          type="button"
          onClick={copy}
          className={cn(
            "flex items-center gap-1.5 rounded-lg px-2 py-1 font-mono text-[11px] font-medium transition-all cursor-pointer",
            copied
              ? "bg-success/20 text-success"
              : "text-slate-400 hover:bg-white/10 hover:text-white"
          )}
          aria-label="Copy code"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy code"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3.5 font-mono text-[13px] leading-relaxed text-slate-100">
        <code>{code}</code>
      </pre>
    </div>
  );
}

/** GFM markdown renderer with copy-code buttons and table styling. */
const markdownComponents: Components = {
  pre: ({ children }) => <>{children}</>,
  code({ className, children }) {
    const match = /language-(\w+)/.exec(className ?? "");
    const text = String(children).replace(/\n$/, "");
    if (match) return <CodeBlock language={match[1]} code={text} />;
    // Inline code: no language class and no line breaks. Everything else is a
    // fenced block and gets the copy button too.
    if (!text.includes("\n")) {
      return (
        <code className="rounded-md border border-border-soft bg-white/[0.06] px-1.5 py-0.5 font-mono text-[12px] text-amber-200">
          {children}
        </code>
      );
    }
    return <CodeBlock language="" code={text} />;
  },
  h1: ({ children }) => <h1 className="mt-3 text-lg font-bold text-white">{children}</h1>,
  h2: ({ children }) => <h2 className="mt-3 text-base font-bold text-white">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-2.5 text-[15px] font-bold text-white">{children}</h3>,
  h4: ({ children }) => <h4 className="mt-2 text-sm font-bold text-white">{children}</h4>,
  p: ({ children }) => <p className="text-slate-200">{children}</p>,
  strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
  em: ({ children }) => <em className="italic text-slate-100">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="font-medium text-primary-soft underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="my-1.5 list-disc space-y-1.5 pl-5 marker:text-primary-soft">{children}</ul>,
  ol: ({ children }) => <ol className="my-1.5 list-decimal space-y-1.5 pl-5 marker:text-primary-soft">{children}</ol>,
  li: ({ children }) => <li className="text-slate-200">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-primary/50 pl-3 text-slate-300 italic">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-border-soft" />,
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto rounded-xl border border-border-soft">
      <table className="w-full border-collapse text-[13px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-white/[0.05]">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-border-soft px-3 py-2 text-left font-bold text-white">{children}</th>
  ),
  td: ({ children }) => <td className="border-b border-border-soft/60 px-3 py-2 text-slate-300">{children}</td>,
  tr: ({ children }) => <tr className="odd:bg-white/[0.02]">{children}</tr>,
};

function MessageBody({ text }: { text: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

type Attachment = { id: string; name: string; mime: string; url: string };
type LocalMessage = AIMessage & { attachments?: string[] };

export function ChatInterface({
  employeeName,
  conversationTitle,
  conversationId,
  initialMessages,
  onNewChat,
}: {
  employeeName: string;
  conversationTitle?: string | null;
  conversationId: string;
  initialMessages: AIMessage[];
  onNewChat?: () => void;
}) {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<LocalMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [dragging, setDragging] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const exportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  // Close the export menu when clicking anywhere else.
  useEffect(() => {
    if (!exportOpen) return;
    function onPointerDown(e: MouseEvent) {
      if (!exportRef.current?.contains(e.target as Node)) setExportOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [exportOpen]);

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
    const assistantMsg: LocalMessage = {
      id: `local-${Date.now() + 1}`,
      conversation_id: conversationId,
      role: "assistant",
      message: "",
    };
    // Append both bubbles up front so the typing dots show while the backend
    // is still generating the reply.
    setMessages((m) => [...m, userMsg, assistantMsg]);

    let reply: string;
    try {
      // Run the AI agent through the backend, which also persists the user
      // message + assistant reply.
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

    const streamed = assistantMsg;
    const chars = reply.split("");
    for (let i = 0; i < chars.length; i++) {
      await new Promise((r) => setTimeout(r, 12));
      setMessages((m) =>
        m.map((msg) => (msg.id === streamed.id ? { ...msg, message: reply.slice(0, i + 1) } : msg))
      );
    }
    setThinking(false);
  }

  // ── Export helpers ───────────────────────────────────────
  function transcriptMarkdown(): string {
    return messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => `### ${m.role === "user" ? "You" : employeeName}\n\n${m.message}\n`)
      .join("\n---\n\n");
  }

  function downloadBlob(content: string, filename: string, type: string) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function copyTranscript() {
    try {
      await navigator.clipboard.writeText(transcriptMarkdown());
      toast.success("Transcript copied to clipboard");
    } catch {
      toast.error("Could not access the clipboard");
    }
    setExportOpen(false);
  }

  function downloadMarkdown() {
    downloadBlob(transcriptMarkdown(), `${conversationTitle ?? "conversation"}.md`, "text/markdown");
    toast.success("Transcript downloaded as Markdown");
    setExportOpen(false);
  }

  function downloadJson() {
    downloadBlob(JSON.stringify(messages, null, 2), `${conversationTitle ?? "conversation"}.json`, "application/json");
    toast.success("Transcript downloaded as JSON");
    setExportOpen(false);
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header: employee identity + New chat / Export actions */}
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border-soft bg-card/60 px-4 py-3 md:px-5">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-secondary">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 truncate text-sm font-bold text-white">
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary-soft" /> {employeeName}
            </p>
            <p className="truncate text-[11px] text-slate-500">{conversationTitle ?? "AI conversation"}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <div className="relative" ref={exportRef}>
            <Button
              variant="ghost"
              size="iconSm"
              aria-label="Export conversation"
              title="Export conversation"
              onClick={() => setExportOpen((o) => !o)}
            >
              <Download className="h-4 w-4" />
            </Button>
            {exportOpen && (
              <div className="absolute right-0 top-full z-30 mt-1.5 w-56 overflow-hidden rounded-xl border border-border-soft bg-card p-1.5 shadow-2xl">
                <p className="px-2.5 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Export transcript
                </p>
                {[
                  { label: "Copy transcript", action: copyTranscript },
                  { label: "Download as Markdown", action: downloadMarkdown },
                  { label: "Download as JSON", action: downloadJson },
                ].map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={item.action}
                    className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-slate-200 transition-colors hover:bg-card-soft hover:text-white"
                  >
                    <Download className="h-3.5 w-3.5 text-slate-500" />
                    {item.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          {onNewChat && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onNewChat}
              title="Start a new conversation"
            >
              <MessageSquarePlus className="h-3.5 w-3.5" /> New chat
            </Button>
          )}
        </div>
      </div>

      {/* Messages (also the drag-and-drop dropzone) */}
      <div
        ref={scrollRef}
        className="relative flex-1 space-y-5 overflow-y-auto p-4 md:p-6 no-scrollbar"
        onDragOver={(e) => {
          e.preventDefault();
          if (!dragging) setDragging(true);
        }}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
      >
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
        {dragging && (
          <div className="pointer-events-none absolute inset-3 z-20 flex items-center justify-center rounded-2xl border-2 border-dashed border-primary/60 bg-primary/10 backdrop-blur-[2px]">
            <div className="flex items-center gap-2 rounded-full bg-card/90 px-4 py-2 text-sm font-semibold text-primary-soft shadow-xl">
              <ImagePlus className="h-4 w-4" /> Drop images to attach
            </div>
          </div>
        )}
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
