"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { localeMeta, type Locale } from "@/i18n/config";
import type { AuthDictionary } from "@/i18n/dictionaries/auth";
import { authApi } from "@/lib/auth/api";
import { classifyAuthError, type ClassifiedError } from "@/lib/auth/errors";
import { fill } from "@/lib/format";

/**
 * Mirrors Django's OTP_REQUEST_COOLDOWN_SECONDS default (60). Display only: Django enforces the
 * real cooldown and answers 429 with Retry-After, which then replaces this value.
 */
const RESEND_COOLDOWN_SECONDS = 60;

type Step = "phone" | "code" | "done";

const inputClass =
  "w-full rounded-lg border border-border bg-background px-3 py-2.5 text-base placeholder:text-muted-foreground";
const primaryButton =
  "inline-flex h-11 w-full items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";
const secondaryButton =
  "inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";

function formatWait(seconds: number, locale: Locale): string {
  const [unit, value] =
    seconds < 60
      ? (["second", seconds] as const)
      : seconds < 3600
        ? (["minute", Math.ceil(seconds / 60)] as const)
        : (["hour", Math.ceil(seconds / 3600)] as const);
  return new Intl.NumberFormat(localeMeta[locale].numberLocale, {
    style: "unit",
    unit,
    unitDisplay: "long",
  }).format(value);
}

export function SignInForm({
  locale,
  t,
  redirectTo,
}: {
  locale: Locale;
  t: AuthDictionary;
  /** Already sanitized on the server (lib/auth/redirect.ts). */
  redirectTo: string;
}) {
  const router = useRouter();
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState<"sending" | "verifying" | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [resent, setResent] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState<number | null>(null);
  const [now, setNow] = useState(0);
  const inFlight = useRef(false); // synchronous guard against double submits
  const alive = useRef(true);
  const phoneInput = useRef<HTMLInputElement>(null);
  const codeInput = useRef<HTMLInputElement>(null);

  const remaining = cooldownUntil === null ? 0 : Math.max(0, Math.ceil((cooldownUntil - now) / 1000));

  useEffect(() => {
    alive.current = true;
    // A customer who is already signed in has nothing to do here.
    authApi
      .me()
      .then((user) => {
        if (user && alive.current) router.replace(redirectTo);
      })
      .catch(() => {});
    return () => {
      alive.current = false;
    };
  }, [router, redirectTo]);

  useEffect(() => {
    if (cooldownUntil === null) return;
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= cooldownUntil) setCooldownUntil(null);
    }, 1000);
    return () => clearInterval(id);
  }, [cooldownUntil]);

  useEffect(() => {
    if (step === "code") codeInput.current?.focus();
    if (step === "phone") phoneInput.current?.focus();
  }, [step]);

  function startCooldown(seconds: number) {
    const t = Date.now();
    setNow(t);
    setCooldownUntil(t + seconds * 1000);
  }

  function message(c: ClassifiedError): string {
    if (c.key === "rate_limited" && c.retryAfterSeconds) {
      return fill(t.errors.rate_limitedWait, { time: formatWait(c.retryAfterSeconds, locale) });
    }
    return t.errors[c.key];
  }

  function clearMessages() {
    setFieldError(null);
    setBanner(null);
    setResent(false);
  }

  async function sendCode(isResend: boolean) {
    if (inFlight.current) return;
    if (!phone.trim()) {
      setBanner(null);
      setFieldError(t.required.phone);
      phoneInput.current?.focus();
      return;
    }
    inFlight.current = true;
    setBusy("sending");
    clearMessages();
    try {
      await authApi.requestOtp(phone.trim());
      if (!alive.current) return;
      setCode("");
      setStep("code");
      startCooldown(RESEND_COOLDOWN_SECONDS);
      setResent(isResend);
    } catch (e) {
      if (!alive.current) return;
      const c = classifyAuthError(e);
      if (c.key === "invalid_phone") {
        setFieldError(message(c));
        phoneInput.current?.focus();
      } else {
        setBanner(message(c));
        if (c.key === "rate_limited" && c.retryAfterSeconds && step === "code") startCooldown(c.retryAfterSeconds);
      }
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(null);
    }
  }

  /** Confirms with Django that the session cookie really works, then leaves. */
  async function finish(): Promise<void> {
    try {
      if ((await authApi.me()) === null) {
        setBanner(t.errors.no_session);
        return;
      }
    } catch {
      // Django already accepted the code; the destination page re-checks the session itself.
    }
    if (!alive.current) return;
    setStep("done");
    router.replace(redirectTo);
  }

  async function verify() {
    if (inFlight.current) return;
    if (!code.trim()) {
      setBanner(null);
      setFieldError(t.required.code);
      codeInput.current?.focus();
      return;
    }
    inFlight.current = true;
    setBusy("verifying");
    clearMessages();
    try {
      await authApi.verifyOtp(phone.trim(), code.trim());
      await finish();
    } catch (e) {
      if (!alive.current) return;
      const c = classifyAuthError(e);
      if (c.key === "network" || c.key === "unexpected") {
        // The outcome is unknown: Django may have created the session before the reply was lost.
        const user = await authApi.me().catch(() => null);
        if (user) return void (await finish());
      }
      if (c.key === "otp_invalid" || c.key === "invalid_code_format") {
        setFieldError(message(c));
        if (c.key === "otp_invalid") setCode("");
        codeInput.current?.focus();
      } else {
        setBanner(message(c));
        if (["otp_expired", "otp_consumed", "otp_attempts_exceeded"].includes(c.key)) {
          setCode("");
          codeInput.current?.focus();
        }
      }
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(null);
    }
  }

  function changeNumber() {
    clearMessages();
    setCode("");
    setStep("phone");
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (step === "phone") void sendCode(false);
    else if (step === "code") void verify();
  }

  if (step === "done") {
    return (
      <section className="mt-6 rounded-lg border border-border p-6" role="status">
        <h2 className="text-xl font-semibold">{t.done.title}</h2>
        <p className="mt-2 text-muted-foreground">{t.done.body}</p>
        <Link href={redirectTo} className={`${secondaryButton} mt-4`}>
          {t.done.continue}
        </Link>
      </section>
    );
  }

  const pending = busy !== null;
  const numberFormat = new Intl.NumberFormat(localeMeta[locale].numberLocale);

  return (
    <form onSubmit={onSubmit} noValidate aria-busy={pending} className="mt-6 grid max-w-md gap-4">
      {banner && (
        <p role="alert" className="rounded-lg border border-border bg-muted px-4 py-3 text-sm">
          {banner}
        </p>
      )}
      {resent && (
        <p role="status" className="text-sm text-muted-foreground">
          {t.code.resent}
        </p>
      )}

      {step === "phone" ? (
        <div className="grid gap-1.5">
          <label htmlFor="signin-phone" className="text-sm font-medium">
            {t.phone.label}
          </label>
          <input
            id="signin-phone"
            ref={phoneInput}
            name="phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            dir="ltr"
            maxLength={32}
            placeholder="09123456789"
            value={phone}
            disabled={pending}
            onChange={(e) => {
              setPhone(e.target.value);
              setFieldError(null);
            }}
            aria-invalid={Boolean(fieldError)}
            aria-describedby={fieldError ? "signin-phone-error" : "signin-phone-hint"}
            className={`${inputClass} text-start`}
          />
          <p id="signin-phone-hint" className="text-xs text-muted-foreground">
            {t.phone.hint}
          </p>
          {fieldError && (
            <p id="signin-phone-error" className="text-sm text-red-700 dark:text-red-400">
              {fieldError}
            </p>
          )}
          <button type="submit" disabled={pending} className={`${primaryButton} mt-2`}>
            {busy === "sending" ? t.phone.submitting : t.phone.submit}
          </button>
        </div>
      ) : (
        <div className="grid gap-1.5">
          <p className="text-sm">
            {t.code.instruction.split("{phone}")[0]}
            <bdi dir="ltr" className="font-medium">
              {phone.trim()}
            </bdi>
            {t.code.instruction.split("{phone}")[1]}
          </p>
          <label htmlFor="signin-code" className="mt-2 text-sm font-medium">
            {t.code.label}
          </label>
          <input
            id="signin-code"
            ref={codeInput}
            name="code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            dir="ltr"
            maxLength={16}
            value={code}
            disabled={pending}
            onChange={(e) => {
              setCode(e.target.value);
              setFieldError(null);
            }}
            aria-invalid={Boolean(fieldError)}
            aria-describedby={fieldError ? "signin-code-error" : "signin-code-hint"}
            className={`${inputClass} text-start tracking-[0.3em]`}
          />
          <p id="signin-code-hint" className="text-xs text-muted-foreground">
            {t.code.hint}
          </p>
          {fieldError && (
            <p id="signin-code-error" className="text-sm text-red-700 dark:text-red-400">
              {fieldError}
            </p>
          )}
          <button type="submit" disabled={pending} className={`${primaryButton} mt-2`}>
            {busy === "verifying" ? t.code.submitting : t.code.submit}
          </button>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void sendCode(true)}
              disabled={pending || remaining > 0}
              className={secondaryButton}
            >
              {remaining > 0
                ? fill(t.code.resendIn, { seconds: numberFormat.format(remaining) })
                : t.code.resend}
            </button>
            <button type="button" onClick={changeNumber} disabled={pending} className={secondaryButton}>
              {t.code.change}
            </button>
          </div>
        </div>
      )}
    </form>
  );
}
