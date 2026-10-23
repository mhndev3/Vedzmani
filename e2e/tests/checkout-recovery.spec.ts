import { expect, test } from "@playwright/test";
import {
  findOrderMatchingSubmission,
  highestOrderId,
  submittedLines,
  type Cart,
  type DeliveryValues,
  type Order,
} from "../../frontend/src/lib/checkout/model";

/**
 * Pure unit tests (no browser, no server): when the outcome of `POST /api/orders/` is unknown, an existing order is
 * attributed to the submission only if it is newer than the baseline AND its delivery fields and lines match.
 */
const SENT: DeliveryValues = {
  recipient_name: "Sara Ahmadi",
  province: "Tehran",
  city: "Tehran",
  address: "Valiasr St, No. 12",
  postal_code: "1234567890",
};
const LINES = [
  { variantSizeId: 11, quantity: 2 },
  { variantSizeId: 12, quantity: 1 },
];

function order(id: number, overrides: Partial<Order> = {}): Order {
  return {
    id,
    status: "pending",
    payment_status: "unpaid",
    customer_phone: "+989120000000",
    ...SENT,
    total: "300000",
    created_at: "2026-10-19T10:00:00Z",
    items: [
      { id: id * 10 + 1, variant_size_id: 11, product_name: "Hoodie", color_name: "Black", size_label: "M", sku: "A", unit_price: "100000", quantity: 2, subtotal: "200000" },
      { id: id * 10 + 2, variant_size_id: 12, product_name: "Tee", color_name: "Black", size_label: "M", sku: "B", unit_price: "100000", quantity: 1, subtotal: "100000" },
    ],
    ...overrides,
  };
}

test.describe("findOrderMatchingSubmission", () => {
  test("returns the order that was created after the baseline with the same delivery and lines", () => {
    expect(findOrderMatchingSubmission([order(8), order(9)], 8, SENT, LINES)?.id).toBe(9);
  });

  test("returns the newest of several matching orders", () => {
    expect(findOrderMatchingSubmission([order(9), order(11), order(10)], 5, SENT, LINES)?.id).toBe(11);
  });

  test("never attributes an order the customer already had (id at or below the baseline)", () => {
    // An identical earlier purchase must not be shown as the result of this submission.
    expect(findOrderMatchingSubmission([order(7), order(8)], 8, SENT, LINES)).toBeNull();
  });

  test("returns null when there are no orders", () => {
    expect(findOrderMatchingSubmission([], 0, SENT, LINES)).toBeNull();
  });

  test("compares the postal code after the server's digit normalization", () => {
    const persian = { ...SENT, postal_code: "۱۲۳۴۵۶۷۸۹۰" };
    expect(findOrderMatchingSubmission([order(9)], 8, persian, LINES)?.id).toBe(9);
    const arabicIndic = { ...SENT, postal_code: "١٢٣٤٥٦٧٨٩٠" };
    expect(findOrderMatchingSubmission([order(9)], 8, arabicIndic, LINES)?.id).toBe(9);
  });

  for (const field of ["recipient_name", "province", "city", "address", "postal_code"] as const) {
    test(`does not match when ${field} differs`, () => {
      expect(findOrderMatchingSubmission([order(9, { [field]: "0987654321x" })], 8, SENT, LINES)).toBeNull();
    });
  }

  test("does not match a different quantity, a different variant, a missing line or an extra line", () => {
    const base = order(9);
    const [first, second] = base.items;
    const cases: Order[] = [
      order(9, { items: [{ ...first, quantity: 3 }, second] }),
      order(9, { items: [{ ...first, variant_size_id: 99 }, second] }),
      order(9, { items: [first] }),
      order(9, { items: [first, second, { ...second, id: 999, variant_size_id: 13 }] }),
    ];
    for (const candidate of cases) {
      expect(findOrderMatchingSubmission([candidate], 8, SENT, LINES)).toBeNull();
    }
  });

  test("does not match when the submission lists the same variant twice", () => {
    const twice = [{ variantSizeId: 11, quantity: 1 }, { variantSizeId: 11, quantity: 1 }];
    expect(findOrderMatchingSubmission([order(9)], 8, SENT, twice)).toBeNull();
  });

  test("prices, totals and statuses are not part of the comparison (Django owns them)", () => {
    const repriced = order(9, { total: "999", status: "pending", payment_status: "unpaid" });
    expect(findOrderMatchingSubmission([repriced], 8, SENT, LINES)?.id).toBe(9);
  });

  test("tolerates a malformed line entry without throwing", () => {
    const broken = order(9, { items: [null as never, null as never] });
    expect(findOrderMatchingSubmission([broken], 8, SENT, LINES)).toBeNull();
  });
});

test.describe("highestOrderId", () => {
  test("is 0 for no orders and the largest id otherwise", () => {
    expect(highestOrderId([])).toBe(0);
    expect(highestOrderId([order(3), order(12), order(7)])).toBe(12);
  });
});

test.describe("submittedLines", () => {
  test("keeps only the variant size id and quantity of each cart line (no prices)", () => {
    const cart = {
      items: [
        { id: 1, quantity: 2, availability: "available", unit_price: "1", subtotal: "2", product: { id: 1, name: "P", slug: "p" }, color: { name: "c", slug: "c", hex_color: "#000" }, variant_size: { id: 11, sku: "A", size: "m", label: "M" } },
      ],
      item_count: 1,
      total_quantity: 2,
      total: "2",
      has_issues: false,
    } satisfies Cart;
    expect(submittedLines(cart)).toEqual([{ variantSizeId: 11, quantity: 2 }]);
  });
});
