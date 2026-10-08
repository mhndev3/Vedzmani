// Static liveness probe for the frontend container. Intentionally does NOT
// call the Django backend so container health is independent of it.
export const dynamic = "force-static";

export function GET() {
  return Response.json({ status: "ok" });
}
