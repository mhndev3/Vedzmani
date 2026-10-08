import Link from "next/link";
import type { Dictionary } from "@/i18n/dictionaries";
import type { HomepageSection } from "@/lib/homepage";

/** Pure presentation: renders whatever the data boundary provides; no business rules. */
export function HomeSection({ section, t }: { section: HomepageSection; t: Dictionary }) {
  const headingId = `home-${section.id}`;
  return (
    <section aria-labelledby={headingId} className="mx-auto max-w-6xl px-4 py-8">
      <h2 id={headingId} className="mb-4 text-xl font-semibold tracking-tight">
        {t.home.sections[section.id]}
      </h2>
      {section.items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border bg-muted px-4 py-10 text-center text-sm text-muted-foreground">
          {t.home.emptySection}
        </p>
      ) : (
        <ul className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {section.items.map((item) => (
            <li key={item.id}>
              <Link
                href={item.href}
                className="block rounded-lg border border-border p-4 hover:bg-muted"
              >
                {item.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
