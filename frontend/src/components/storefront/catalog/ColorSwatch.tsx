import type { CSSProperties } from "react";

const NAMED_COLORS: Record<string, string> = {
  "مشکی": "#171717", "سیاه": "#171717", "black": "#171717",
  "سفید": "#ffffff", "white": "#ffffff",
  "طوسی": "#888888", "خاکستری": "#888888", "خاکستری روشن": "#d1d5db", "طوسی روشن": "#d1d5db", "gray": "#888888", "grey": "#888888",
  "ذغالی": "#343a40", "زغالی": "#343a40", "charcoal": "#343a40",
  "قرمز": "#dc2626", "زرشکی": "#800020", "عنابی": "#800020", "red": "#dc2626", "maroon": "#800020",
  "آبی": "#2563eb", "آبی روشن": "#60a5fa", "سرمه ای": "#172554", "سرمه‌ای": "#172554", "آبی نفتی": "#164e63", "blue": "#2563eb", "navy": "#172554",
  "سبز": "#16a34a", "سبز روشن": "#86efac", "زیتونی": "#6b7132", "یشمی": "#047857", "green": "#16a34a", "olive": "#6b7132",
  "قهوه ای": "#78350f", "قهوه‌ای": "#78350f", "نسکافه ای": "#a16207", "نسکافه‌ای": "#a16207", "کرم": "#e8d8b8", "بژ": "#d6c3a1", "شکلاتی": "#5b3827", "brown": "#78350f", "beige": "#d6c3a1",
  "صورتی": "#ec4899", "گلبهی": "#f4a28c", "pink": "#ec4899",
  "زرد": "#eab308", "لیمویی": "#d9e650", "yellow": "#eab308",
  "نارنجی": "#f97316", "orange": "#f97316",
  "بنفش": "#9333ea", "یاسی": "#c4b5fd", "purple": "#9333ea",
  "طلایی": "#c9a227", "نقره ای": "#c0c0c0", "نقره‌ای": "#c0c0c0",
};

function normalize(value: string): string {
  return value.trim().replace(/[يى]/g, "ی").replace(/ك/g, "ک").replace(/\s+/g, " ");
}

export function resolveColor(hexColor?: string | null, name?: string): string {
  const hex = hexColor?.trim() ?? "";
  if (/^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(hex)) return hex;
  const normalized = normalize(name ?? "");
  return NAMED_COLORS[normalized] ?? NAMED_COLORS[normalized.toLowerCase()] ?? "#a1a1aa";
}

export function ColorSwatch({
  name,
  hexColor,
  className = "size-3.5",
  productCode,
  colorIndex,
}: {
  name: string;
  hexColor?: string | null;
  className?: string;
  productCode?: string | null;
  colorIndex?: number;
}) {
  const code = productCode?.trim().split(/[.-]/)[0];
  const twoToneColors: Record<string, [string, string]> = {
    "02": ["#ffffff", "#006b4f"],
    "03": ["#9ca3af", "#343a40"],
    "04": ["#171717", "#dc2626"],
  };
  const twoTone = code ? twoToneColors[code] : undefined;
  const isSkyBlueFirst = code === "05" && colorIndex === 0 && normalize(name) === "آبی آسمانی";
  const isShirtWhiteSecond = code === "01" && colorIndex === 1;
  const style: CSSProperties = twoTone
    ? { background: `linear-gradient(135deg, ${twoTone[0]} 0 50%, ${twoTone[1]} 50% 100%)` }
    : { backgroundColor: isSkyBlueFirst ? "#a8d8f0" : isShirtWhiteSecond ? "#e5e7eb" : resolveColor(hexColor, name) };
  return (
    <span
      aria-hidden="true"
      title={name}
      className={`block shrink-0 rounded-[3px] border border-black/15 shadow-sm ${className}`}
      style={style}
    />
  );
}
