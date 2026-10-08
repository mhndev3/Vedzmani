from rest_framework.pagination import PageNumberPagination


class CatalogPagination(PageNumberPagination):
    """Bounded page-number pagination: default 24, hard cap 60 (never an unlimited result set)."""

    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 60
