import "server-only";
import type { Locale } from "../config";
import { fa, type Dictionary } from "./fa";
import { en } from "./en";

const dictionaries: Record<Locale, Dictionary> = { fa, en };

export type { Dictionary };

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale];
}
