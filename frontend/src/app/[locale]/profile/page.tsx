import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { SignInLink } from "@/components/auth/SignInLink";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { SavedProducts } from "@/components/profile/SavedProducts";
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
    <div className="mx-auto w-full max-w-4xl px-4 py-10">
      <h1 className="flex items-center justify-center gap-3 text-center text-2xl font-bold tracking-tight sm:text-3xl"><span aria-hidden="true" className="flex items-center gap-1.5"><i className="size-1.5 rounded-full bg-current" /><i className="size-1.5 rounded-full bg-current" /><i className="size-1.5 rounded-full bg-current" /></span><span>{t.profile.title}</span><span aria-hidden="true" className="flex items-center gap-1.5"><i className="size-1.5 rounded-full bg-current" /><i className="size-1.5 rounded-full bg-current" /><i className="size-1.5 rounded-full bg-current" /></span></h1>
      {state.kind === "ok" && (
        <>
          <dl className="mt-6 text-sm">
            <dt className="text-muted-foreground">{t.profile.phone}</dt>
            <dd className="mt-1" dir="ltr" style={{ textAlign: "start" }}>{state.profile.phone}</dd>
          </dl>
          <ProfileForm initialProfile={state.profile} locale={locale} continueTo={continueTo} />
          <SavedProducts locale={locale} t={t} />
        </>
      )}
      {state.kind === "anonymous" && (
        <section className="mx-auto mt-8 flex min-h-[340px] w-full max-w-2xl flex-col items-center justify-center rounded-3xl border border-border bg-card px-6 py-12 text-center shadow-sm sm:min-h-[380px] sm:px-12" aria-labelledby="profile-signed-out-title">
          <div aria-hidden="true" className="mb-6 grid size-20 place-items-center rounded-full bg-muted text-foreground">
            <svg viewBox="0 0 24 24" className="size-10" fill="none">
              <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.7" />
              <path d="M5 20c.7-3.5 3.2-5.5 7-5.5s6.3 2 7 5.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </div>
          <h2 id="profile-signed-out-title" className="text-xl font-bold sm:text-2xl">{t.profile.signedOut}</h2>
          <p className="mt-3 max-w-md text-base leading-8 text-muted-foreground">{t.profile.signedOutHint}</p>
          <div className="mt-7">
            <SignInLink locale={locale} next={continueTo} className="inline-flex h-12 items-center justify-center rounded-xl bg-primary px-8 text-base font-semibold text-primary-foreground transition hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring" />
          </div>
        </section>
      )}
      {state.kind === "error" && (
        <p role="status" className="mt-4 text-muted-foreground">
          {t.profile.unavailable}
        </p>
      )}
    </div>
  );
}
