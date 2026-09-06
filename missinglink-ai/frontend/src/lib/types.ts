export type Role = "PUBLIC_USER" | "INVESTIGATOR" | "ADMIN";

export interface UserProfile {
  id: number;
  email: string;
  fullName: string;
  role: Role;
  status: string;
  createdAt: string;
  permissions: string[];
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  user: UserProfile;
}

export type CaseStatus = "ACTIVE" | "CRITICAL" | "RESOLVED" | "CLOSED";
export type Priority = "STANDARD" | "HIGH" | "CRITICAL";

export interface MissingCase {
  id: string;
  caseReference?: string;
  fullName?: string;
  firstName?: string;
  lastName?: string;
  age?: number;
  sex?: string;
  gender?: string;
  status: CaseStatus;
  priority: Priority;
  lastKnownLocation?: string;
  lastKnownPlace?: string;
  lastKnownAt?: string;
  lastKnownLat?: number;
  lastKnownLng?: number;
  isPublic?: boolean;
  createdAt: string;
}

export interface TimelineEntry {
  eventType: string;
  description?: string;
  actorName?: string;
  createdAt: string;
}

export interface Photo {
  id: number;
  filename: string;
  contentUrl?: string;
  uploadedBy: string;
  uploadedAt: string;
}

export interface Match {
  id: number;
  caseReference: string;
  sightingReference: string;
  overallScore: number;
  status: string;
  createdAt: string;
  warning?: string;
}

export interface Sighting {
  id: number;
  description?: string;
  capturedAt?: string;
  status?: string;
  lat?: number;
  lng?: number;
  reporterName?: string;
  createdAt?: string;
  matchCount?: number;
}

export interface GeoPoint {
  lat: number;
  lng: number;
  accuracyMeters?: number;
  capturedAt?: string;
  description?: string;
  count?: number;
}

export interface Notification {
  id: number;
  type: string;
  message: string;
  read: boolean;
  createdAt: string;
}

export interface CaseDetail {
  id: string;
  status: string;
  priority: string;
  fullName: string;
  age?: number;
  sex?: string;
  heightCm?: number;
  lastKnownLocation?: string;
  lastKnownAt?: string;
  description?: string;
  timeline: TimelineEntry[];
  photos: Photo[];
  matches: Match[];
}
