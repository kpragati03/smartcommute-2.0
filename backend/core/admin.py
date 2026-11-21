from django.contrib import admin
from .models import Organisation, User, Membership, AuditLog

admin.site.register(Organisation)
admin.site.register(User)
admin.site.register(Membership)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "action", "actor", "organisation", "object_type", "object_id", "created_at"]
    list_filter = ["action", "organisation"]
    search_fields = ["action", "object_type", "object_id", "detail"]
    readonly_fields = ["actor", "organisation", "action", "object_type", "object_id", "detail", "created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
