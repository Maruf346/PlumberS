from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import (
    ContactSupport,
    FAQ,
    AboutUs,
    TermsAndConditions,
    PrivacyPolicy
)


# ==============================
# Contact Support Admin
# ==============================

@admin.register(ContactSupport)
class ContactSupportAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "user",
        "email",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("subject", "email", "user__email", "user__username")
    readonly_fields = ("id", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # Usually support requests are created by users, not admin
        return False


# ==============================
# FAQ Admin
# ==============================

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "created_at", "updated_at")
    search_fields = ("question", "answer")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)


# ==============================
# Singleton Base Admin
# ==============================

class SingletonAdmin(admin.ModelAdmin):
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Prevent adding more than one instance
        if self.model.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion (optional but recommended for singleton models)
        return False


# ==============================
# About Us Admin
# ==============================

@admin.register(AboutUs)
class AboutUsAdmin(SingletonAdmin):
    pass


# ==============================
# Terms & Conditions Admin
# ==============================

@admin.register(TermsAndConditions)
class TermsAndConditionsAdmin(SingletonAdmin):
    pass


# ==============================
# Privacy Policy Admin
# ==============================

@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(SingletonAdmin):
    pass


from django.contrib import admin
from .models import Feedback, IssueReport


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'country', 'language', 'user', 'created_at']
    list_filter = ['country', 'language']
    search_fields = ['first_name', 'last_name', 'email', 'user__email']
    readonly_fields = ['id', 'user', 'created_at', 'updated_at']


@admin.register(IssueReport)
class IssueReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'photo_count', 'created_at']
    search_fields = ['title', 'user__email', 'user__full_name']
    readonly_fields = [
        'id', 'user', 'photo_count',
        'created_at', 'updated_at'
    ]