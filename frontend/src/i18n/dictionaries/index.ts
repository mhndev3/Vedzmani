import "server-only";
import type { Locale } from "../config";
import { fa, type Dictionary } from "./fa";

export type { Dictionary };

export function getDictionary(_locale: Locale): Dictionary {
  return fa;
}
