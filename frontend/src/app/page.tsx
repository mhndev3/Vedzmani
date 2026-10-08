import { apiGet } from "@/lib/api";

// Rendered per request so the page reflects live backend state.
export const dynamic = "force-dynamic";

type Health = { status: string };

async function getBackendStatus(): Promise<"ok" | "unreachable"> {
  try {
    const data = await apiGet<Health>("/api/health/");
    return data.status === "ok" ? "ok" : "unreachable";
  } catch {
    return "unreachable";
  }
}

/** Foundation smoke page. NOT the Vedzmani storefront. */
export default async function Home() {
  const backend = await getBackendStatus();
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 px-6">
      <p className="text-muted-foreground text-sm tracking-widest uppercase">
        Foundation
      </p>
      <h1 className="text-4xl font-semibold tracking-tight">Vedzmani</h1>
      <p className="text-muted-foreground">
        Next.js frontend is running. Storefront features arrive in later
        sessions.
      </p>
      <p data-testid="backend-status" className="text-sm">
        Backend API: <strong>{backend}</strong>
      </p>
    </main>
  );
}