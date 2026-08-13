"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Check, KeyRound, Loader2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/shared/logo";
import { supabase } from "@/lib/supabase/client";
import { toast } from "sonner";

/**
 * Password reset page. Supabase's recovery email links to
 * `<origin>/reset-password#access_token=…&refresh_token=…&type=recovery`.
 * We read the tokens from the hash, restore the session, and let the user set
 * a new password via supabase.auth.updateUser.
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Defer state updates past the first paint so the initial client render
    // matches the server HTML (no hydration mismatch / lint violation).
    const frame = requestAnimationFrame(() => {
      const params = new URLSearchParams(window.location.hash.slice(1));
      const accessToken = params.get("access_token");
      const refreshToken = params.get("refresh_token");
      if (accessToken) {
        supabase.auth
          .setSession({ access_token: accessToken, refresh_token: refreshToken ?? "" })
          .then(({ error }) => {
            if (error) setInvalid(true);
            else setReady(true);
          });
      } else {
        setInvalid(true);
      }
      // Strip the tokens from the URL bar so they don't linger in history.
      window.history.replaceState({}, "", window.location.pathname);
    });
    return () => cancelAnimationFrame(frame);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    if (password !== confirm) {
      toast.error("Passwords do not match");
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password });
    if (error) {
      setLoading(false);
      toast.error(error.message);
      return;
    }
    // Drop the recovery session so the old password can't be reused.
    await supabase.auth.signOut();
    toast.success("Password updated — sign in with your new password.");
    router.push("/login");
  }

  return (
    <div className="dark relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-6 py-12">
      <div className="absolute inset-0 bg-mesh" />
      <div className="absolute inset-0 bg-grid" />

      <div className="relative z-10 w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Link href="/"><Logo /></Link>
        </div>

        <div className="rounded-2xl border border-border-soft bg-card p-8 shadow-2xl shadow-black/40">
          {ready ? (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent shadow-lg shadow-primary/25">
                <KeyRound className="h-6 w-6 text-white" />
              </div>
              <h1 className="mt-5 text-2xl font-bold tracking-tight text-white">Set a new password</h1>
              <p className="mt-1.5 text-sm text-slate-400">
                Choose a strong password (8+ characters) for your account.
              </p>

              <form onSubmit={handleSubmit} className="mt-7 space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="password">New password</Label>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <Input
                      id="password"
                      type="password"
                      required
                      minLength={8}
                      placeholder="Min 8 characters"
                      className="pl-10"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm">Confirm password</Label>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <Input
                      id="confirm"
                      type="password"
                      required
                      minLength={8}
                      placeholder="Repeat password"
                      className="pl-10"
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                    />
                  </div>
                  {confirm.length > 0 && (
                    <p className={`text-[10px] font-bold uppercase tracking-wide ${password === confirm ? "text-success" : "text-danger"}`}>
                      {password === confirm ? "✓ Match" : "✗ Does not match"}
                    </p>
                  )}
                </div>
                <Button type="submit" size="lg" className="w-full" disabled={loading}>
                  {loading ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Updating…</>
                  ) : (
                    <><Check className="h-4 w-4" /> Update password</>
                  )}
                </Button>
              </form>
            </>
          ) : invalid ? (
            <>
              <h1 className="text-2xl font-bold tracking-tight text-white">Link invalid or expired</h1>
              <p className="mt-2 text-sm text-slate-400">
                This password-reset link is missing, invalid, or has expired. Request a new one from the
                sign-in page.
              </p>
              <Link href="/login" className="mt-6 block">
                <Button size="lg" className="w-full">Back to sign in</Button>
              </Link>
            </>
          ) : (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-primary-soft" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
