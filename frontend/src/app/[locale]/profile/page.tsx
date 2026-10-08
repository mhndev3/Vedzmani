import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { ApiError, apiGet } from "@/lib/api";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: getDictionary(locale).profile.title } : {};
}

type Me = { id: number | string; phone: string; is_staff: boolean };
type MeState = { kind: "anonymous" } | { kind: "ok"; me: Me } | { kind: "error" };

/** Reads the existing Django session (Agent 3). No auth logic is duplicated here. */
async function getMe(): Promise<MeState> {
  const sessionId = (await cookies()).get("sessionid")?.value;
  if (!sessionId) return { kind: "anonymous" };
  try {
    const me = await apiGet<Me>("/api/auth/me/", {
      headers: { Cookie: `sessionid=${sessionId}` },
    });
    return { kind: "ok", me };
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return { kind: "anonymous" };
    return { kind: "error" };
  }
}

export default async function ProfilePage({ params }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const state = await getMe();

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{t.profile.title}</h1>
      {state.kind === "ok" && (
        <dl className="mt-6 text-sm">
          <dt className="text-muted-foreground">{t.profile.phone}</dt>
          <dd className="mt-1" dir="ltr" style={{ textAlign: "start" }}>
            {state.me.phone}
          </dd>
        </dl>
      )}
      {state.kind === "anonymous" && (
        <div className="mt-4">
          <p>{t.profile.signedOut}</p>
          <p className="mt-2 text-muted-foreground">{t.profile.signedOutHint}</p>
        </div>
      )}
      {state.kind === "error" && (
        <p role="status" className="mt-4 text-muted-foreground">
          {t.profile.unavailable}
        </p>
      )}
    </div>
  );
}
