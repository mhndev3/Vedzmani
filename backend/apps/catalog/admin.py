"""Minimal inspection-only registrations. The full admin belongs to the admin agent."""

from django.contrib import admin

from . import models

admin.site.register(models.Category)
admin.site.register(models.Collection)
admin.site.register(models.Size)
admin.site.register(models.Product)
admin.site.register(models.ColorVariant)
admin.site.register(models.VariantSize)
admin.site.register(models.VariantImage)
