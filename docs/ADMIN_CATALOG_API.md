# API مدیریت کاتالوگ

این API برای پنل اختصاصی مدیریت ودزمانی است و زیر مسیر `/api/admin/` قرار دارد. مسیرهای عمومی `/api/catalog/` بدون تغییر باقی مانده‌اند.

## احراز هویت و مجوزها

- احراز هویت با نشست Django فعلی انجام می‌شود؛ درخواست‌های تغییردهنده باید CSRF معتبر داشته باشند.
- هر endpoint هم‌زمان به حساب فعال با `is_staff` و مجوز مدل متناظر Django نیاز دارد. داشتن نشست، `is_staff` یا مجوز مدل به‌تنهایی کافی نیست.
- برای هر عملیات باید مجوز مدل متناظر Django به کاربر یا گروه او داده شود؛ مانند `catalog.view_product`، `catalog.add_product` و `catalog.change_product`.
- مجوزهای حذف به‌تنهایی endpoint حذف ایجاد نمی‌کنند. در این مرحله حذف سخت از API ارائه نشده و انتشار/عدم انتشار با `is_active` مدیریت می‌شود.

## مسیرها

| مسیر | مدل | عملیات |
|---|---|---|
| `GET/POST /api/admin/catalog/products/` | Product | فهرست و ایجاد |
| `GET/PUT/PATCH /api/admin/catalog/products/{id}/` | Product | مشاهده و ویرایش |
| `/api/admin/catalog/categories/` | Category | فهرست، ایجاد، مشاهده و ویرایش |
| `/api/admin/catalog/collections/` | Collection | فهرست، ایجاد، مشاهده و ویرایش |
| `/api/admin/catalog/sizes/` | Size | فهرست، ایجاد، مشاهده و ویرایش |
| `/api/admin/catalog/colors/` | ColorVariant | فهرست، ایجاد، مشاهده و ویرایش |
| `/api/admin/catalog/variant-sizes/` | VariantSize | فهرست، ایجاد، مشاهده و ویرایش |
| `/api/admin/catalog/product-measurements/` | ProductSizeMeasurement | اندازه‌های مشترک محصول و سایز |
| `/api/admin/catalog/variant-size-measurements/` | VariantSizeMeasurement | اندازه اختصاصی رنگ و سایز |
| `GET /api/admin/catalog/images/` | VariantImage | مشاهده فراداده تصاویر |
| `GET/POST /api/admin/inventory/adjustments/` | InventoryAdjustment | مشاهده تاریخچه و ثبت گردش موجودی |

## قواعد محافظت‌شده

- `ColorVariant.product_code` فقط خواندنی است و با شمارنده تراکنشی فعلی مدل تولید می‌شود.
- `VariantSize.stock_quantity` فقط خواندنی است. ثبت تغییر موجودی علاوه بر `inventory.add_inventoryadjustment` به `catalog.view_variantsize` نیاز دارد و باید از `apps.inventory.services.adjust_stock` عبور کند تا قفل ردیف، کنترل مقدار منفی و سابقه تغییر در یک تراکنش ثبت شوند.
- تصویرها در این مرحله فقط فراداده خواندنی دارند. آپلود فایل، پردازش WebP و مدیریت کلیدهای ذخیره‌سازی باید در مرحله جداگانه با اعتبارسنجی فایل و اتصال به pipeline فعلی تصویر پیاده‌سازی شود؛ کلید ذخیره‌سازی از API عمومی قابل نوشتن نیست.
- مدل‌ها و دیتابیس تغییر نکرده‌اند؛ این مرحله migration جدید ندارد.
- سفارش‌ها و پرداخت SEP تحت تأثیر این API نیستند و وضعیت غیرفعال فعلی آن‌ها حفظ می‌شود.
