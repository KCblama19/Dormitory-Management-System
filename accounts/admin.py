from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import User
from accounts.forms.adminCreateForm import UserAdminForm
import uuid


# ==========================================
# Custom Admin Class
# ==========================================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Fully customized admin panel for User model.

    Extends Django's built-in UserAdmin to support:
    - Role-based identity system
    - Multiple identifiers
    - Clean UI
    """

    form = UserAdminForm

    # --------------------------------------
    # List View (Table)
    # --------------------------------------
    list_display = (
        "username",
        "role",
        "student_id",
        "staff_id",
        "email",
        "is_claimed",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "role",
        "is_claimed",
        "is_staff",
        "is_active",
    )

    search_fields = (
        "username",
        "student_id",
        "staff_id",
        "email",
        "phone_number",
    )

    ordering = ("username",)

    # --------------------------------------
    # Edit Page Layout
    # --------------------------------------
    fieldsets = (
        ("Core Identity", {
            "fields": ("username", "password", "role")
        }),

        ("Identifiers", {
            "fields": ("student_id", "staff_id", "email", "phone_number")
        }),

        ("Verification", {
            "fields": ("is_claimed", "date_of_birth")
        }),

        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),

        ("Important Dates", {
            "fields": ("last_login", "date_joined")
        }),
    )

    # --------------------------------------
    # Add User Page Layout
    # --------------------------------------
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username",
                "password1",
                "password2",
                "role",
                "student_id",
                "staff_id",
                "email",
                "phone_number",
                "date_of_birth",
            ),
        }),
    )

    readonly_fields = ("last_login", "date_joined")

    # ======================================
    # AUTO USERNAME GENERATION
    # ======================================
    def save_model(self, request, obj, form, change):
        """
        Automatically generate a username if not provided.

        Why:
        - The system does NOT rely on username as real identity
        - So we generate a unique internal one
        """

        if not obj.username:
            obj.username = self.generate_username(obj)

        super().save_model(request, obj, form, change)

    def generate_username(self, obj):
        """
        Generates a unique system username.

        Strategy:
        - Use role prefix
        - Append short UUID
        """

        prefix = {
            User.UserType.STUDENT: "STU",
            User.UserType.STAFF: "STF",
            User.UserType.ADMIN: "ADM",
        }.get(obj.role, "USR")

        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    # ======================================
    # DYNAMIC FIELD DISPLAY (ROLE-AWARE UI)
    # ======================================
    def get_fieldsets(self, request, obj=None):
        """
        Dynamically adjust fields based on role.

        This improves admin UX by hiding irrelevant fields.
        """

        fieldsets = super().get_fieldsets(request, obj)

        if obj:
            if obj.role == User.UserType.STUDENT:
                fieldsets[1][1]["fields"] = (
                    "student_id",
                    "email",
                    "phone_number",
                )

            elif obj.role in [User.UserType.STAFF, User.UserType.ADMIN]:
                fieldsets[1][1]["fields"] = (
                    "staff_id",
                    "email",
                    "phone_number",
                )

        return fieldsets