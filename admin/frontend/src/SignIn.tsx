import { type FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { useAuth, type User } from "@/stores/auth";
import { errorText } from "@app/lib/format";
import { Button, ErrorNote, Field, Input } from "@app/ui";

export default function SignIn({ notice }: { notice?: string }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(notice ?? null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { access_token } = await api.post<{ access_token: string }>("/auth/login", { username, password });
      useAuth.getState().setToken(access_token);
      const me = await api.get<User>("/auth/me");
      if (!me.is_superadmin && me.role !== "superadmin") {
        useAuth.getState().logout();
        setError("This account can't use the admin panel. Ask a teammate to give you access.");
        return;
      }
      useAuth.getState().setUser(me);
    } catch (err) {
      useAuth.getState().logout();
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-svh place-items-center bg-rail px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-xl bg-white p-7 shadow-2xl">
        <div className="mb-6">
          <div className="text-[11px] font-bold tracking-[0.1em] text-ox uppercase">Mizan Admin</div>
          <h1 className="mt-1 text-xl font-bold tracking-[-0.02em] text-ink">Sign in to manage the platform</h1>
          <p className="mt-1 text-[13px] text-mute">For the Mizan team. Workspace owners sign in to the app instead.</p>
        </div>
        <div className="grid gap-4">
          <Field label="Username">
            <Input autoComplete="username" autoFocus required value={username} onChange={(e) => setUsername(e.target.value)} />
          </Field>
          <Field label="Password">
            <Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
        </div>
        {error && <ErrorNote>{error}</ErrorNote>}
        <Button type="submit" variant="primary" busy={busy} className="mt-6 w-full">
          Sign in
        </Button>
      </form>
    </div>
  );
}
