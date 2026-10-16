/**
 * Checkout types and input checks.
 *
 * Source of truth: backend/ORDERS.md (`POST /api/orders/`) and backend/CART.md.
 * Everything here is a CONVENIENCE for faster feedback only. Django validates
 * again and is authoritative for the delivery details, prices, stock, totals
 * and order state. Nothing in this module computes money.
 */

export const DELIVERY_FIELDS = [
  "recipient_name",
  "province",
  "city",
  "address",
  "postal_code",
] as const;

export type DeliveryField = (typeof DELIVERY_FIELDS)[number];
export type DeliveryValues = Record<DeliveryField, string>;

/** Maximum lengths documented in ORDERS.md (characters, after trimming). */
export const MAX_LENGTH: Record<DeliveryField, number> = {
  recipient_name: 120,
  province: 60,
  city: 60,
  address: 255,
  postal_code: 10,
};

export const EMPTY_DELIVERY: DeliveryValues = {
  recipient_name: "",
  province: "",
  city: "",
  address: "",
  postal_code: "",
};

export type FieldError = "required" | "too_long" | "invalid_postal_code" | "invalid_characters" | "invalid";
export type FieldErrors = Partial<Record<DeliveryField, FieldError>>;

// Persian (U+06F0..) and Arabic-Indic (U+0660..) digits -> ASCII, as the server does.
function toAsciiDigits(value: string): string {
  return value.replace(/[\u06F0-\u06F9\u0660-\u0669]/g, (ch) => {
    const code = ch.charCodeAt(0);
    return String(code >= 0x06f0 ? code - 0x06f0 : code - 0x0660);
  });
}

const CONTROL_CHARS = /[\u0000-\u001F\u007F-\u009F\u2028\u2029]/;

export function validateDelivery(values: DeliveryValues): FieldErrors {
  const errors: FieldErrors = {};
  for (const field of DELIVERY_FIELDS) {
    const raw = values[field];
    const trimmed = raw.trim();
    if (CONTROL_CHARS.test(raw)) errors[field] = "invalid_characters";
    else if (trimmed === "") errors[field] = "required";
    else if (field === "postal_code") {
      if (!/^[0-9]{10}$/.test(toAsciiDigits(trimmed))) errors[field] = "invalid_postal_code";
    } else if (trimmed.length > MAX_LENGTH[field]) errors[field] = "too_long";
  }
  return errors;
}

/** Maps a server `details.<field>[].code` onto the small set the UI can word. */
export function fieldErrorFromServerCode(code: string): FieldError {
  switch (code) {
    case "required":
    case "blank":
    case "null":
      return "required";
    case "max_length":
      return "too_long";
    case "invalid_postal_code":
      return "invalid_postal_code";
    case "control_characters":
      return "invalid_characters";
    default:
      return "invalid";
  }
}

// --- API shapes (read-only views of what Django returns) -------------------

export type Me = { id: number | string; phone: string; is_staff: boolean };

export type CartItem = {
  id: number;
  quantity: number;
  availability: "available" | "insufficient_stock" | "unavailable" | string;
  unit_price: string;
  subtotal: string;
  product: { id: number; name: string; slug: string };
  color: { name: string; slug: string; hex_color: string };
  variant_size: { id: number; sku: string; size: string; label: string };
};

export type Cart = {
  items: CartItem[];
  item_count: number;
  total_quantity: number;
  total: string;
  has_issues: boolean;
};

export type OrderItem = {
  id: number;
  variant_size_id: number;
  product_name: string;
  color_name: string;
  size_label: string;
  sku: string;
  unit_price: string;
  quantity: number;
  subtotal: string;
};

export type Order = {
  id: number;
  status: string;
  payment_status: string;
  customer_phone: string;
  recipient_name: string;
  province: string;
  city: string;
  address: string;
  postal_code: string;
  total: string;
  created_at: string;
  items: OrderItem[];
};

/** A 201 body is only treated as a confirmed order when it has this shape. */
export function isConfirmedOrder(value: unknown): value is Order {
  if (typeof value !== "object" || value === null) return false;
  const o = value as Record<string, unknown>;
  return (
    typeof o.id === "number" &&
    typeof o.total === "string" &&
    typeof o.status === "string" &&
    Array.isArray(o.items)
  );
}
