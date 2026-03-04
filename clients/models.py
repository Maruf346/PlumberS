from django.db import models
import uuid


class Client(models.Model):
    """
    Clients are added manually by admin.
    They do not have platform accounts.
    Address is stored as plain text but exposed as a maps hyperlink
    in the frontend (admin dashboard + mobile app).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core details
    name = models.CharField(max_length=150, help_text="Client company or individual name")
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    profile_picture = models.ImageField(upload_to='clients/pictures/', null=True, blank=True)

    # Address stored as text; frontend builds the maps hyperlink
    address = models.CharField(
        max_length=500,
        help_text="Full address — rendered as Google Maps hyperlink in app and dashboard"
    )

    # Contact person (on-site representative)
    contact_person_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Name of the on-site contact person"
    )

    # Site access info (gate codes, access instructions, etc.)
    site_access = models.TextField(
        blank=True,
        help_text="e.g. Gate B, Code 4589 — access instructions for staff"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def maps_url(self):
        """Google Maps search URL built from address."""
        from urllib.parse import quote
        return f"https://www.google.com/maps/search/?api=1&query={quote(self.address)}"

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['name']