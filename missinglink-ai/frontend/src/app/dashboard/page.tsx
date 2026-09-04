"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isInvestigator } from "@/lib/roles";
import CaseCard from "@/components/CaseCard";
import MatchCard from "@/components/MatchCard";
import RequireAuth from "@/components/RequireAuth";
import type { MissingCase, Match, Notification } from "@/lib/types";

function DashboardBody() {
  const { user } = useAuth();
  const [cases, setCases] = useState<MissingCase[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<MissingCase[]>("/cases")
      .then(setCases)
      .catch((e) => setError(e.message));
    api<Notification[]>("/notifications")
      .then(setNotifications)
      .catch(() => undefined);
    if (isInvestigator(user)) {
      api<Match[]>("/matches").then(setMatches).catch(() => undefined);
    }
  }, [user]);

  const unread = notifications.filter((n) => !n.read).length;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brand-ink">
            Welcome, {user?.fullName}
          </h1>
          <p className="text-sm text-slate-500">
            {isInvestigator(user)
              ? "Case queue, match reviews and notifications."
              : "Your missing-person reports and notifications."}
          </p>
        </div>
        {isInvestigator(user) && (
          <Link href="/queue" className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-dark">
            Review queue
          </Link>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl bg-brand-ink p-5 text-white">
          <p className="text-3xl font-black">{cases.length}</p>
          <p className="text-sm text-blue-100">Cases</p>
        </div>
        {isInvestigator(user) && (
          <div className="rounded-xl bg-slate-800 p-5 text-white">
            <p className="text-3xl font-black">{matches.length}</p>
            <p className="text-sm text-slate-300">Leads awaiting review</p>
          </div>
        )}
        <div className="rounded-xl bg-amber-100 p-5 text-amber-900">
          <p className="text-3xl font-black">{unread}</p>
          <p className="text-sm">Unread notifications</p>
        </div>
      </div>

      {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      <section>
        <h2 className="mb-3 text-lg font-bold text-brand-ink">
          {isInvestigator(user) ? "Active cases" : "Your reports"}
        </h2>
        {cases.length === 0 ? (
          <p className="text-sm text-slate-400">
            No cases yet.{" "}
            <Link href="/report" className="text-brand hover:underline">
              Report a missing person
            </Link>
            .
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {cases.map((c) => (
              <Link key={c.id} href={`/cases/${c.id}`}>
                <CaseCard item={c} />
              </Link>
            ))}
          </div>
        )}
      </section>

      {isInvestigator(user) && matches.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-bold text-brand-ink">Newest leads</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {matches.slice(0, 6).map((m) => (
              <MatchCard key={m.id} item={m} />
            ))}
          </div>
        </section>
      )}

      {notifications.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-bold text-brand-ink">Notifications</h2>
          <ul className="space-y-2">
            {notifications.slice(0, 8).map((n) => (
              <li key={n.id} className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
                <span className="font-medium">{n.message}</span>
                <span className="ml-2 text-xs text-slate-400">
                  {new Date(n.createdAt).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardBody />
    </RequireAuth>
  );
}
