"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { isInvestigator } from "@/lib/roles";

const links = [
  { href: "/", label: "Home" },
  { href: "/map", label: "Map" },
  { href: "/report", label: "Report a missing person" },
  { href: "/sighting", label: "Submit a sighting" },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  const nav = user ? (
    <>
      <Link href="/photo-match" className={pathname.startsWith("/photo-match") ? "text-amber-300" : "hover:text-amber-200"}>
        Face match
      </Link>
      {isInvestigator(user) && (
        <>
          <Link href="/dashboard" className={pathname.startsWith("/dashboard") ? "text-amber-300" : "hover:text-amber-200"}>
            Dashboard
          </Link>
          <Link href="/queue" className={pathname.startsWith("/queue") ? "text-amber-300" : "hover:text-amber-200"}>
            Match queue
          </Link>
        </>
      )}
      <span className="text-sm text-blue-100">{user.fullName}</span>
      <button
        onClick={() => logout()}
        className="rounded bg-white/10 px-3 py-1 text-sm hover:bg-white/20"
      >
        Sign out
      </button>
    </>
  ) : (
    <>
      <Link href="/login" className="hover:text-amber-200">
        Sign in
      </Link>
      <Link href="/register" className="rounded bg-white px-3 py-1 text-sm font-semibold text-brand-ink hover:bg-amber-100">
        Create account
      </Link>
    </>
  );

  return (
    <header className="bg-brand-ink text-white shadow-lg">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-400 font-black text-brand-ink">
            M
          </span>
          <span className="text-lg font-bold tracking-tight">MissingLink</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={pathname === l.href ? "text-amber-300" : "hover:text-amber-200"}
            >
              {l.label}
            </Link>
          ))}
          {nav}
        </nav>
      </div>
    </header>
  );
}
