export type AuthResponse = {
  id: string;
  email: string;
  email_verified: boolean;
  display_name: string | null;
  staff_role: string;
  totp_enabled: boolean;
  mfa_verified: boolean;
};

export async function authPost<T>(path: string, body: Record<string, string>): Promise<T> {
  const csrfResponse = await fetch("/api/auth/csrf", { credentials: "include" });
  if (!csrfResponse.ok) throw new Error("Could not start a secure sign-in request. Please try again.");
  const { csrf_token: csrfToken } = (await csrfResponse.json()) as { csrf_token: string };
  const response = await fetch(`/api/auth/${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-RC-CSRF": csrfToken },
    body: JSON.stringify(body),
  });
  const payload = (await response.json().catch(() => ({}))) as { detail?: string } & T;
  if (!response.ok) throw new Error(payload.detail ?? "Request failed. Please try again.");
  return payload;
}
