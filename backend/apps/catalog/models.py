"""Product domain foundation.

Category -> Product -> ColorVariant -> (VariantImage[], VariantSize)
Collection <-> Product (M2M)

PostgreSQL is the source of truth. Inventory *business logic* (decrement,
reservation, checkout validation) belongs to the inventory agent; this module
only gives each purchasable (product, color, size) row an addressable
`VariantSize` and a non-negative `stock_quantity` column to build on.
"""

from decimal import Decimal

from django.conf import settings

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator, validate_slug
from django.db import models, transaction
from django.db.models import F, Q

from .storage import ALLOWED_IMAGE_CONTENT_TYPES, public_image_url
from .validators import validate_hex_color, validate_storage_key


def category_image_upload_to(instance, filename):
    import os
    import uuid

    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".img"
    return f"categories/{uuid.uuid4().hex}{extension}"


class Category(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to=category_image_upload_to, blank=True, default="")
    product_fields = models.JSONField(default=list, blank=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Collection(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return self.name


class Size(models.Model):
    """Controlled size vocabulary (S, M, 42, ...). Not hard-coded in the frontend."""

    code = models.CharField(max_length=20, unique=True, validators=[validate_slug])
    label = models.CharField(max_length=40)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return self.label


class Product(models.Model):
    """`price` is the base/list price; `sale_price` the optional current price.

    All prices are stored as whole Toman units (never Rials or floats).
    The product owns the price; color variants do not have separate prices.
    """

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    collections = models.ManyToManyField(Collection, blank=True, related_name="products")
    product_code = models.CharField(max_length=40, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=0, validators=[MinValueValidator(Decimal("1"))])
    sale_price = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("1"))],
    )
    is_active = models.BooleanField(default=False)  # unpublished until explicitly activated
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name="product_price_positive"),
            models.CheckConstraint(
                condition=Q(sale_price__isnull=True) | (Q(sale_price__gt=0) & Q(sale_price__lt=F("price"))),
                name="product_sale_price_valid",
            ),
        ]
        indexes = [
            # storefront listing: active products of a category, newest first
            models.Index(fields=["category", "is_active", "-created_at"], name="product_cat_active_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def current_price(self) -> Decimal:
        return self.sale_price if self.sale_price is not None else self.price


class ProductSizeMeasurement(models.Model):
    """One flexible measurement row for a product and a size, shared by its colors."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="size_measurements")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="product_measurements")
    name = models.CharField(max_length=80)
    value = models.CharField(max_length=80)
    unit = models.CharField(max_length=30, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["size__position", "position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "position"],
                name="product_size_measurement_unique_position",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.size_id}:{self.name}"


class ProductSizeDescription(models.Model):
    """Optional description for one size of a product, shared by all colors."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="size_descriptions")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="product_descriptions")
    description = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "size"], name="product_size_description_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.size_id}"


class ColorVariantCodeCounter(models.Model):
    """Transactional counter for globally unique numeric storefront card codes."""

    next_value = models.PositiveIntegerField(default=1)


class ColorVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="color_variants")
    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=80)
    product_code = models.CharField(
        "کد کارت محصول",
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(regex=r"^\d+$", message="کد کارت باید فقط شامل عدد باشد.")],
    )
    hex_color = models.CharField(max_length=7, blank=True, validators=[validate_hex_color])
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.product_code and not self.product_code.isdecimal():
            raise ValidationError({"product_code": "کد کارت باید فقط شامل عدد باشد."})
        if self.product_code:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            counter, _ = ColorVariantCodeCounter.objects.select_for_update().get_or_create(
                pk=1,
                defaults={"next_value": 1},
            )
            self.product_code = str(counter.next_value).zfill(2)
            counter.next_value += 1
            counter.save(update_fields=["next_value"])
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"product_code"}
            return super().save(*args, **kwargs)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "slug"], name="colorvariant_unique_product_slug"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.slug}"


class VariantSize(models.Model):
    """The exact purchasable unit: product + color + size.

    Cart items / order items reference this row. `stock_quantity` is a plain
    persisted column; only the inventory module may mutate it (atomically).
    """

    variant = models.ForeignKey(ColorVariant, on_delete=models.CASCADE, related_name="sizes")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="variant_sizes")
    sku = models.CharField(max_length=64, unique=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["size__position", "size_id"]
        constraints = [
            models.UniqueConstraint(fields=["variant", "size"], name="variantsize_unique_variant_size"),
        ]

    def __str__(self) -> str:
        return self.sku


class VariantSizeDescription(models.Model):
    """Optional override for one exact color + size purchasable combination."""

    variant_size = models.OneToOneField(
        VariantSize, on_delete=models.CASCADE, related_name="description"
    )
    description = models.TextField()

    def __str__(self) -> str:
        return f"{self.variant_size_id}:description"


class VariantSizeMeasurement(models.Model):
    """Measurement row for one exact color + size.

    When a purchasable size has any of these rows they are the measurements shown for that color + size and
    replace the product-level rows (`ProductSizeMeasurement`), which stay the shared fallback for all colors.
    """

    variant_size = models.ForeignKey(VariantSize, on_delete=models.CASCADE, related_name="measurements")
    name = models.CharField(max_length=80)
    value = models.CharField(max_length=80)
    unit = models.CharField(max_length=30, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["variant_size", "position"],
                name="variant_size_measurement_unique_position",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.variant_size_id}:{self.name}"


class VariantImage(models.Model):
    """Image metadata only. Binary lives in S3-compatible storage behind a CDN."""

    CONTENT_TYPE_CHOICES = [(ct, ct) for ct in ALLOWED_IMAGE_CONTENT_TYPES]

    variant = models.ForeignKey(ColorVariant, on_delete=models.CASCADE, related_name="images")
    storage_key = models.CharField(max_length=500, unique=True, validators=[validate_storage_key])
    # Original media is immutable; responsive WebP copies use separate cache-safe storage keys.
    thumbnail_storage_key = models.CharField(max_length=500, blank=True, default="", validators=[validate_storage_key])
    display_storage_key = models.CharField(max_length=500, blank=True, default="", validators=[validate_storage_key])
    optimization_version = models.PositiveSmallIntegerField(default=0)
    alt_text = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    width = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    height = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    content_type = models.CharField(max_length=50, choices=CONTENT_TYPE_CHOICES, default="image/webp")
    file_size = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            # deterministic order: no two images share a slot within a variant
            models.UniqueConstraint(fields=["variant", "position"], name="variantimage_unique_variant_position"),
            # at most one primary image per variant
            models.UniqueConstraint(
                fields=["variant"], condition=Q(is_primary=True), name="variantimage_one_primary_per_variant"
            ),
            models.CheckConstraint(
                condition=Q(width__gt=0) & Q(height__gt=0), name="variantimage_dimensions_positive"
            ),
            models.CheckConstraint(
                condition=Q(content_type__in=ALLOWED_IMAGE_CONTENT_TYPES), name="variantimage_content_type_allowed"
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            old_key = type(self).objects.filter(pk=self.pk).values_list("storage_key", flat=True).first()
            if old_key and old_key != self.storage_key:
                self.thumbnail_storage_key = ""
                self.display_storage_key = ""
                self.optimization_version = 0
                update_fields = kwargs.get("update_fields")
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {
                        "thumbnail_storage_key", "display_storage_key", "optimization_version"
                    }
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.storage_key

    @property
    def url(self) -> str:
        return public_image_url(self.storage_key)


class Favorite(models.Model):
    """A customer-owned saved product. Favorites never expose data across accounts."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorite_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="catalog_favorite_user_product_uniq"),
        ]
        indexes = [models.Index(fields=["user", "-created_at"], name="favorite_user_created_idx")]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.product_id}"


class HomepageSection(models.Model):
    """Configurable homepage section. Drafts are stored independently of storefront rendering."""

    TYPE_CATEGORIES = "categories"
    TYPE_PRODUCTS = "products"
    TYPE_NEWEST_PRODUCTS = "newest_products"
    TYPE_CHOICES = [
        (TYPE_CATEGORIES, "Category grid"),
        (TYPE_PRODUCTS, "Selected products"),
        (TYPE_NEWEST_PRODUCTS, "Newest products"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [(STATUS_DRAFT, "Draft"), (STATUS_PUBLISHED, "Published")]

    title = models.CharField(max_length=120)
    eyebrow = models.CharField(max_length=120, blank=True)
    section_type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    position = models.PositiveIntegerField(default=0)
    item_limit = models.PositiveSmallIntegerField(default=8)
    show_view_all = models.BooleanField(default=True)
    view_all_url = models.CharField(max_length=240, blank=True)
    categories = models.ManyToManyField(Category, blank=True, related_name="homepage_sections")
    products = models.ManyToManyField(Product, blank=True, related_name="homepage_sections")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["status", "position"], name="home_section_status_pos_idx"),
        ]

    def __str__(self) -> str:
        return self.title



class HomepageSectionRevision(models.Model):
    """Immutable snapshot of a homepage section configuration."""

    ACTION_BASELINE = "baseline"
    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_ROLLBACK = "rollback"
    ACTION_CHOICES = [
        (ACTION_BASELINE, "Baseline"),
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_ROLLBACK, "Rollback"),
    ]

    section = models.ForeignKey(HomepageSection, on_delete=models.CASCADE, related_name="revisions")
    snapshot = models.JSONField()
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="homepage_section_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["section", "-created_at"], name="home_section_rev_idx")]

    def __str__(self) -> str:
        return f"{self.section_id}:{self.action}:{self.pk}"


def homepage_banner_upload_to(instance, filename):
    import os
    import uuid

    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".img"
    return f"homepage-banners/{uuid.uuid4().hex}{extension}"


class HomepageBannerGroup(models.Model):
    """Named collection of banners rendered together as one homepage slider."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name


def default_homepage_banner_group():
    group, _ = HomepageBannerGroup.objects.get_or_create(
        slug="main",
        defaults={"name": "بنرهای اصلی", "position": 0, "is_active": True},
    )
    return group.pk


class HomepageBanner(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [(STATUS_DRAFT, "Draft"), (STATUS_PUBLISHED, "Published")]

    title = models.CharField(max_length=120, blank=True)
    subtitle = models.CharField(max_length=240, blank=True)
    alt_text = models.CharField(max_length=200)
    group = models.ForeignKey(
        HomepageBannerGroup,
        on_delete=models.PROTECT,
        related_name="banners",
        default=default_homepage_banner_group,
    )
    desktop_image = models.ImageField(upload_to=homepage_banner_upload_to)
    mobile_image = models.ImageField(upload_to=homepage_banner_upload_to, blank=True)
    cta_label = models.CharField(max_length=60, blank=True)
    cta_url = models.CharField(max_length=240, blank=True)
    position = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [models.Index(fields=["status", "position"], name="home_banner_status_pos_idx")]

    def __str__(self):
        return self.title or f"Homepage banner #{self.pk}"

def default_storefront_theme_settings():
    return {
        "primary": "#171717",
        "primary_foreground": "#fafafa",
        "accent": "#e5e5e5",
        "accent_foreground": "#171717",
        "font": "system",
        "radius": "medium",
        "motion": "standard",
    }


class StorefrontTheme(models.Model):
    """Singleton draft/published design tokens for the public storefront."""

    draft_settings = models.JSONField(default=default_storefront_theme_settings)
    published_settings = models.JSONField(default=default_storefront_theme_settings)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "storefront theme"
        verbose_name_plural = "storefront theme"

    def __str__(self):
        return "Storefront theme"


class HomepageBannerRevision(models.Model):
    """Immutable content and media-reference snapshot for a homepage banner."""

    ACTION_BASELINE = "baseline"
    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_ROLLBACK = "rollback"
    ACTION_CHOICES = [
        (ACTION_BASELINE, "Baseline"),
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_ROLLBACK, "Rollback"),
    ]

    banner = models.ForeignKey(HomepageBanner, on_delete=models.CASCADE, related_name="revisions")
    snapshot = models.JSONField()
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="homepage_banner_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["banner", "-created_at"], name="home_banner_rev_idx")]


class StorefrontThemeRevision(models.Model):
    """Immutable snapshot of storefront draft and published design tokens."""

    ACTION_BASELINE = "baseline"
    ACTION_DRAFT = "draft_saved"
    ACTION_PUBLISHED = "published"
    ACTION_ROLLBACK = "rollback"
    ACTION_CHOICES = [
        (ACTION_BASELINE, "Baseline"),
        (ACTION_DRAFT, "Draft saved"),
        (ACTION_PUBLISHED, "Published"),
        (ACTION_ROLLBACK, "Rollback"),
    ]

    theme = models.ForeignKey(StorefrontTheme, on_delete=models.CASCADE, related_name="revisions")
    snapshot = models.JSONField()
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="storefront_theme_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["theme", "-created_at"], name="store_theme_rev_idx")]
