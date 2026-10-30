import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { SignInLink } from "@/components/auth/SignInLink";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { ApiError, apiGet } from "@/lib/api";
import { safeRedirectPath } from "@/lib/auth/redirect";

type Props = { params: Promise<{ locale: string }>; searchParams: Promise<{ next?: string | string[] }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: getDictionary(locale).profile.title } : {};
}

type Profile = { id: number; phone: string; first_name: string; last_name: string; address: string; postal_code: string; national_code: string | null; is_complete: boolean };
type MeState = { kind: "anonymous" } | { kind: "ok"; profile: Profile } | { kind: "error" };

/** Reads the existing Django session (Agent 3). No auth logic is duplicated here. */
async function getMe(): Promise<MeState> {
  const sessionId = (await cookies()).get("sessionid")?.value;
  if (!sessionId) return { kind: "anonymous" };
  try {
    const profile = await apiGet<Profile>("/api/auth/profile/", {
      headers: { Cookie: `sessionid=${sessionId}` },
    });
    return { kind: "ok", profile };
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return { kind: "anonymous" };
    return { kind: "error" };
  }
}

export default async function ProfilePage({ params, searchParams }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = getDictionary(locale);
  const { next } = await searchParams;
  const continueTo = safeRedirectPath(next, locale);
  const state = await getMe();

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{t.profile.title}</h1>
      {state.kind === "ok" && (
        <>
          <dl className="mt-6 text-sm">
            <dt className="text-muted-foreground">{t.profile.phone}</dt>
            <dd className="mt-1" dir="ltr" style={{ textAlign: "start" }}>{state.profile.phone}</dd>
          </dl>
          <ProfileForm initialProfile={state.profile} locale={locale} continueTo={continueTo} />
        </>
      )}
      {state.kind === "anonymous" && (
        <div className="mt-4">
          <p>{t.profile.signedOut}</p>
          <p className="mt-2 text-muted-foreground">{t.profile.signedOutHint}</p>
          <div className="mt-4">
            <SignInLink locale={locale} next={continueTo} />
          </div>
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
