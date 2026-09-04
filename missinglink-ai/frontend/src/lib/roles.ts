import type { UserProfile } from "@/lib/types";

export function hasPermission(user: UserProfile | null, permission: string): boolean {
  return !!user?.permissions?.includes(permission);
}

export function isInvestigator(user: UserProfile | null): boolean {
  return user?.role === "INVESTIGATOR" || user?.role === "ADMIN";
}
