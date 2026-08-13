"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Mail, Lock, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  fetchUserOrgId,
  fetchUserRoles,
  PENDING_WORKSPACE_KEY,
  signIn,
} from "@/hooks/use-session";
import { homePathForRoles } from "@/lib/roles";
import { supabase } from "@/lib/supabase/client";
import { api } from "@/lib/api/client";
import { toast } from "sonner";
import { motion } from "framer-motion";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [sendingReset, setSendingReset] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  /**
   * Finish a workspace whose org could not be created at signup because email
   * confirmation delayed the session. Returns whether the org was created and
   * any error that prevented it. The pending payload is kept on failure so the
   * next sign-in can retry.
   */
  async function finishPendingWorkspace(userId: string): Promise<{
    created: boolean;
    error: string | null;
  }> {
    const raw = localStorage.getItem(PENDING_WORKSPACE_KEY);
    if (!raw) return { created: false, error: null };
    try {
      const orgId = await fetchUserOrgId(userId);
      if (orgId) {
        // Already in an org — nothing to create.
        localStorage.removeItem(PENDING_WORKSPACE_KEY);
        return { created: false, error: null };
      }
      const workspace = JSON.parse(raw) as {
        name: string;
        slug: string;
        country: string;
        industry?: string;
      };
      await api.createOrganization(workspace);
      localStorage.removeItem(PENDING_WORKSPACE_KEY);
      return { created: true, error: null };
    } catch (err) {
      return { created: false, error: (err as Error).message || "Could not create your workspace" };
    }
  }

  /** Shared: sign in with Supabase, then redirect by the user's role. */
  async function signInAndRedirect(email: string, password: string, successMessage: string) {
    setLoading(true);
    try {
      await signIn(email, password);

      // Role-based redirect: Owners/Admins land on the dashboard, Employees on
      // their tasks. A user without roles yet (e.g. before workspace setup)
      // goes to the dashboard to finish onboarding.
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;
      const roles = await fetchUserRoles(session.user.id);

      // Signups delayed by email confirmation finish their workspace here.
      const { created, error: workspaceError } = await finishPendingWorkspace(
        session.user.id
      );
      if (created) {
        toast.success("Workspace created! Welcome aboard 🎉");
        router.push("/dashboard");
        return;
      }
      if (workspaceError) {
        toast.error(workspaceError);
        router.push(homePathForRoles(roles));
        return;
      }

      toast.success(successMessage);
      router.push(homePathForRoles(roles));
    } catch (err) {
      toast.error((err as Error).message || "Invalid credentials");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await signInAndRedirect(email, password, "Welcome back!");
  }

  /** Send a Supabase password-recovery link to the entered email. */
  async function handleForgotPassword() {
    if (!email.trim()) {
      toast.error("Enter your email address first.");
      return;
    }
    setSendingReset(true);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
        // The recovery link lands here; the page reads the token and lets the
        // user set a new password. Add this origin to Supabase → Auth → URL
        // Configuration → Redirect URLs for production.
        redirectTo: `${window.location.origin}/reset-password`,
      });
      if (error) throw error;
      setResetSent(true);
      toast.success("Password reset link sent — check your inbox.");
    } catch (err) {
      toast.error((err as Error).message || "Could not send the reset link");
    } finally {
      setSendingReset(false);
    }
  }

  async function handleOAuth(provider: "google" | "azure") {
    toast.info("Redirecting to sign-in…");
    // Supabase OAuth flows are wired via the Supabase project; the URL is
    // configured there (https://supabase.com/dashboard -> Auth -> URL Configuration).
    const { error } = await supabase.auth.signInWithOAuth({ provider });
    if (error) toast.error(error.message);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        <Button type="button" variant="secondary" onClick={() => handleOAuth("google")}>
          <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.1A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.1V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15A11 11 0 0 0 2.18 7.06L5.84 9.9C6.71 7.31 9.14 5.38 12 5.38z" />
          </svg>
          Google
        </Button>
        <Button type="button" variant="secondary" onClick={() => handleOAuth("azure")}>
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
            <rect x="2" y="2" width="9.5" height="9.5" fill="#f25022" />
            <rect x="12.5" y="2" width="9.5" height="9.5" fill="#7fba00" />
            <rect x="2" y="12.5" width="9.5" height="9.5" fill="#00a4ef" />
            <rect x="12.5" y="12.5" width="9.5" height="9.5" fill="#ffb900" />
          </svg>
          Microsoft
        </Button>
      </div>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border-soft" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-card px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            or continue with email
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <div className="relative">
          <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <Input
            id="email"
            type="email"
            required
            placeholder="you@company.com"
            className="pl-10"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="password">Password</Label>
          <button
            type="button"
            onClick={handleForgotPassword}
            disabled={sendingReset}
            className="text-xs font-semibold text-primary-soft hover:text-white transition-colors cursor-pointer disabled:opacity-50"
          >
            {sendingReset ? "Sending…" : "Forgot password?"}
          </button>
        </div>
        <div className="relative">
          <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <Input
            id="password"
            type="password"
            required
            placeholder="••••••••"
            className="pl-10"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
      </div>

      <motion.div whileTap={{ scale: 0.98 }}>
        <Button type="submit" className="w-full" size="lg" disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Sign in <ArrowRight className="h-4 w-4" /></>}
        </Button>
      </motion.div>

      {resetSent && (
        <p className="rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-xs text-green-300">
          Reset link sent to <span className="font-bold">{email.trim()}</span> — check your inbox, then
          use the link to set a new password.
        </p>
      )}

      <p className="text-center text-sm text-slate-500">
        Don&apos;t have an account?{" "}
        <button
          type="button"
          onClick={() => router.push("/register")}
          className="font-bold text-primary-soft hover:text-white transition-colors cursor-pointer"
        >
          Create workspace
        </button>
      </p>
    </form>
  );
}
