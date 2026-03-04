from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    # Full access — is_superuser=True.
    message = 'Admin access required.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsManager(BasePermission):
    # Manager access — is_staff=True, is_superuser=False.
    message = 'Manager access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_staff and
            not request.user.is_superuser
        )


class IsEmployee(BasePermission):
    # Employee access — is_staff=False, is_superuser=False.
    message = 'Employee access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            not request.user.is_staff and
            not request.user.is_superuser
        )


class IsAdminOrManager(BasePermission):
    # Admin or Manager — any staff-level user.
    message = 'Admin or Manager access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_staff  # both manager and admin have is_staff=True
        )


class IsAdminOrManagerOrEmployee(BasePermission):
    # Any authenticated internal user.
    message = 'Authentication required.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsAdminOrReadOnly(BasePermission):
    # Admin can do anything.
    # Others (authenticated) can only read (GET, HEAD, OPTIONS).

    message = 'Admin access required for write operations.'

    SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in self.SAFE_METHODS:
            return True
        return request.user.is_superuser


class IsOwnerOrAdmin(BasePermission):
    # Object-level: only the owner of the object or an admin can access.
    # The view must set obj.user or obj.owner to the related user.

    message = 'You do not have permission to access this resource.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        # Support both .user and .owner patterns
        owner = getattr(obj, 'user', None) or getattr(obj, 'owner', None)
        return owner == request.user