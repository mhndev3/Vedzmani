"""Superuser-only staff role management for the custom admin workspace.

Roles are Django Groups. The API exposes only a deliberately curated set of
store-operation permissions; it never exposes auth, user-management, payment,
or arbitrary model permissions. Staff access changes are audited with
privacy-safe before/after snapshots.
"""
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import OTP_SESSION_FLAG
from .models import AdminAuditEvent, User


# Only permissions used by the current admin workspace are assignable here.
# In particular, no auth.* permissions, user add/change/delete permissions,
# superuser controls, or payment permissions are exposed.
MANAGED_PERMISSION_MODELS = {
    "accounts": {
        "supportticket": {"view", "change"},
        "supportticketmessage": {"add"},
        "adminauditevent": {"view"},
        "user": {"view"},
    },
    "catalog": {
        "category": {"view", "add", "change"},
        "collection": {"view", "add", "change"},
        "size": {"view", "add", "change"},
        "product": {"view", "add", "change"},
        "colorvariant": {"view", "add", "change"},
        "variantsize": {"view", "add", "change"},
        "variantimage": {"view", "add", "change"},
        "productsizemeasurement": {"view", "add", "change"},
        "productsizedescription": {"view", "add", "change"},
        "variantsizemeasurement": {"view", "add", "change"},
        "variantsizedescription": {"view", "add", "change"},
        "homepagebanner": {"view", "add", "change"},
        "homepagebannergroup": {"view", "add", "change"},
        "homepagesection": {"view", "add", "change"},
        "storefronttheme": {"view", "change"},
    },
    "orders": {
        "order": {"view", "view_order_pii"},
        "orderitem": {"view"},
        "shippingmethod": {"view", "add", "change"},
    },
    "inventory": {"inventoryadjustment": {"view", "add"}},
}


def _permission_key(permission):
    return f"{permission.content_type.app_label}.{permission.codename}"


def _managed_permissions():
    rows = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "content_type__model", "codename"
    )
    result = []
    for permission in rows:
        app_label = permission.content_type.app_label
        model = permission.content_type.model
        actions = MANAGED_PERMISSION_MODELS.get(app_label, {}).get(model, set())
        if any(permission.codename == f"{action}_{model}" for action in actions):
            result.append(permission)
        elif app_label == "orders" and model == "order" and permission.codename == "view_order_pii":
            result.append(permission)
    return result


def _permission_map():
    return {_permission_key(item): item for item in _managed_permissions()}


def _group_permissions(group, allowed=None):
    allowed = allowed if allowed is not None else _permission_map()
    current = list(group.permissions.select_related("content_type").all())
    # Do not expose or allow assignment of a group carrying permissions outside
    # the curated workspace allowlist (for example auth or account-admin powers).
    if any(_permission_key(item) not in allowed for item in current):
        return None
    return sorted(_permission_key(item) for item in current)


def _group_payload(group, allowed=None):
    permissions = _group_permissions(group, allowed)
    return {
        "id": group.pk,
        "name": group.name,
        "permissions": permissions or [],
        "member_count": group.user_set.count(),
        "manageable": permissions is not None,
    }


def _staff_payload(user, allowed=None):
    safe_groups = []
    unmanaged_count = 0
    for group in user.groups.all():
        permissions = _group_permissions(group, allowed)
        if permissions is not None:
            safe_groups.append({"id": group.pk, "name": group.name})
        else:
            unmanaged_count += 1
    return {
        "id": user.pk,
        "label": f"مدیر #{user.pk}",
        "is_active": user.is_active,
        "roles": safe_groups,
        "unmanaged_role_count": unmanaged_count,
    }


def _resolve_permissions(keys):
    if not isinstance(keys, list) or len(keys) > 80:
        return None
    if any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys):
        return None
    available = _permission_map()
    if any(key not in available for key in keys):
        return None
    return [available[key] for key in keys]


def _role_snapshot(group):
    return {
        "id": group.pk,
        "name": group.name,
        "permissions": _group_permissions(group) or [],
    }


def _record_access_change(request, *, action, path, entity_type, entity_id, before, after, response_status=200):
    AdminAuditEvent.objects.create(
        actor=request.user,
        action=action,
        method=request.method,
        path=path[:255],
        entity_type=entity_type,
        entity_id=entity_id,
        response_status=response_status,
        details={"before": before, "after": after},
    )


def _can_manage(request):
    user = request.user
    return bool(
        user and user.is_authenticated and user.is_active
        and user.is_staff and user.is_superuser
        and not request.session.get(OTP_SESSION_FLAG)
    )


class SuperuserStaffPermission(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and _can_manage(request)


@method_decorator(never_cache, name="dispatch")
class AdminStaffRoleListView(APIView):
    permission_classes = [SuperuserStaffPermission]

    def get(self, request):
        allowed = _permission_map()
        groups = Group.objects.prefetch_related("permissions__content_type", "user_set").order_by("name", "id")
        return Response({
            "results": [_group_payload(group, allowed) for group in groups if _group_permissions(group, allowed) is not None],
            "permissions": [{
                "key": key,
                "app": item.content_type.app_label,
                "model": item.content_type.model,
                "name": item.name,
            } for key, item in sorted(allowed.items())],
        })

    def post(self, request):
        name = request.data.get("name")
        permission_keys = request.data.get("permissions", [])
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            return Response({"error": {"code": "invalid_role_name"}}, status=400)
        permissions = _resolve_permissions(permission_keys)
        if permissions is None:
            return Response({"error": {"code": "invalid_role_permissions"}}, status=400)
        name = name.strip()
        if Group.objects.filter(name__iexact=name).exists():
            return Response({"error": {"code": "role_name_exists"}}, status=409)
        with transaction.atomic():
            group = Group.objects.create(name=name)
            group.permissions.set(permissions)
            _record_access_change(
                request, action="post", path="/api/admin/staff/roles/",
                entity_type="staff_role", entity_id=group.pk,
                before={}, after=_role_snapshot(group), response_status=201,
            )
        return Response(_group_payload(group), status=201)


@method_decorator(never_cache, name="dispatch")
class AdminStaffRoleDetailView(APIView):
    permission_classes = [SuperuserStaffPermission]

    def patch(self, request, role_id):
        group = get_object_or_404(Group.objects.prefetch_related("permissions__content_type"), pk=role_id)
        before = _role_snapshot(group)
        if _group_permissions(group) is None:
            return Response({"error": {"code": "role_has_unmanaged_permissions"}}, status=409)
        name = request.data.get("name", group.name)
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            return Response({"error": {"code": "invalid_role_name"}}, status=400)
        name = name.strip()
        if Group.objects.exclude(pk=group.pk).filter(name__iexact=name).exists():
            return Response({"error": {"code": "role_name_exists"}}, status=409)
        permissions = None
        if "permissions" in request.data:
            permissions = _resolve_permissions(request.data["permissions"])
            if permissions is None:
                return Response({"error": {"code": "invalid_role_permissions"}}, status=400)
        with transaction.atomic():
            group.name = name
            group.save(update_fields=["name"])
            if permissions is not None:
                group.permissions.set(permissions)
            group.refresh_from_db()
            _record_access_change(
                request, action="patch", path=f"/api/admin/staff/roles/{group.pk}/",
                entity_type="staff_role", entity_id=group.pk,
                before=before, after=_role_snapshot(group),
            )
        return Response(_group_payload(group))

    def delete(self, request, role_id):
        group = get_object_or_404(Group.objects.prefetch_related("permissions__content_type"), pk=role_id)
        if _group_permissions(group) is None:
            return Response({"error": {"code": "role_has_unmanaged_permissions"}}, status=409)
        if group.user_set.exists():
            return Response({"error": {"code": "role_in_use"}}, status=409)
        before = _role_snapshot(group)
        group_id = group.pk
        with transaction.atomic():
            group.delete()
            _record_access_change(
                request, action="delete", path=f"/api/admin/staff/roles/{group_id}/",
                entity_type="staff_role", entity_id=group_id,
                before=before, after={},
            )
        return Response(status=204)


@method_decorator(never_cache, name="dispatch")
class AdminStaffListView(APIView):
    permission_classes = [SuperuserStaffPermission]

    def get(self, request):
        allowed = _permission_map()
        staff = User.objects.filter(is_staff=True, is_superuser=False).prefetch_related(
            "groups__permissions__content_type"
        ).order_by("id")
        return Response({"results": [_staff_payload(user, allowed) for user in staff]})


@method_decorator(never_cache, name="dispatch")
class AdminStaffRoleAssignmentView(APIView):
    permission_classes = [SuperuserStaffPermission]

    def patch(self, request, staff_id):
        role_ids = request.data.get("role_ids")
        if (
            not isinstance(role_ids, list) or len(role_ids) > 30
            or any(not isinstance(value, int) or isinstance(value, bool) for value in role_ids)
            or len(set(role_ids)) != len(role_ids)
        ):
            return Response({"error": {"code": "invalid_role_ids"}}, status=400)
        user = get_object_or_404(
            User.objects.prefetch_related("groups__permissions__content_type"),
            pk=staff_id, is_staff=True, is_superuser=False,
        )
        allowed = _permission_map()
        groups = list(Group.objects.filter(pk__in=role_ids).prefetch_related("permissions__content_type"))
        if len(groups) != len(role_ids) or any(_group_permissions(group, allowed) is None for group in groups):
            return Response({"error": {"code": "invalid_role_ids"}}, status=400)
        current_groups = list(user.groups.all())
        managed_current_groups = [
            group for group in current_groups
            if _group_permissions(group, allowed) is not None
        ]
        before = _staff_payload(user, allowed)["roles"]
        with transaction.atomic():
            # Touch only groups managed by this workspace. External groups are
            # deliberately left attached and are never passed through set()/clear().
            if managed_current_groups:
                user.groups.remove(*managed_current_groups)
            if groups:
                user.groups.add(*groups)
            user.refresh_from_db()
            after = _staff_payload(user, allowed)["roles"]
            _record_access_change(
                request, action="patch", path=f"/api/admin/staff/{user.pk}/roles/",
                entity_type="staff_user_roles", entity_id=user.pk,
                before=before, after=after,
            )
        return Response(_staff_payload(user, allowed))
