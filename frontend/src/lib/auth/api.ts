import { BrowserApiError, apiRequest } from "@/lib/browser-api";
export type AuthUser = { id: number; phone: string; is_staff: boolean };
export type CustomerProfile = { id: number; phone: string; first_name: string; last_name: string; address: string; postal_code: string; national_code: string | null; is_complete: boolean };
export type CustomerProfileInput = { first_name: string; last_name: string; address: string; postal_code: string; national_code: string };
const UNEXPECTED = () => new BrowserApiError(200, "unexpected_response");
function isRecord(v: unknown): v is Record<string, unknown> { return typeof v === "object" && v !== null; }
function isAuthUser(v: unknown): v is AuthUser { return isRecord(v) && typeof v.id === "number" && typeof v.phone === "string" && typeof v.is_staff === "boolean"; }
export const authApi = {
  async requestOtp(phone: string): Promise<void> { const body = await apiRequest<unknown>("POST", "/api/auth/otp/request/", { phone }); if (!isRecord(body) || typeof body.detail !== "string") throw UNEXPECTED(); },
  async verifyOtp(phone: string, code: string): Promise<{ user: AuthUser; isNewUser: boolean }> { const body = await apiRequest<unknown>("POST", "/api/auth/otp/verify/", { phone, code }); if (!isRecord(body) || !isAuthUser(body.user)) throw UNEXPECTED(); return { user: body.user, isNewUser: body.is_new_user === true }; },
  async login(phone: string, password: string): Promise<AuthUser> { const body = await apiRequest<unknown>("POST", "/api/auth/password/login/", { phone, password }); if (!isRecord(body) || !isAuthUser(body.user)) throw UNEXPECTED(); return body.user; },
  async setPassword(password: string): Promise<void> { const body = await apiRequest<unknown>("POST", "/api/auth/password/set/", { password }); if (!isRecord(body) || typeof body.detail !== "string") throw UNEXPECTED(); },
  async profile(): Promise<CustomerProfile> { return apiRequest<CustomerProfile>("GET", "/api/auth/profile/"); },
  async updateProfile(profile: Partial<CustomerProfileInput>): Promise<CustomerProfile> { return apiRequest<CustomerProfile>("PATCH", "/api/auth/profile/", profile); },
  async logout(): Promise<void> { await apiRequest<void>("POST", "/api/auth/logout/"); },
  async me(): Promise<AuthUser | null> { try { const body = await apiRequest<unknown>("GET", "/api/auth/me/"); if (!isAuthUser(body)) throw UNEXPECTED(); return body; } catch (e) { if (e instanceof BrowserApiError && e.status === 401) return null; throw e; } },
};
