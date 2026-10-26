from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", default=None, read_only=True)

    class Meta:
        model = AuditLog
        fields = ("id", "timestamp", "user", "action", "model_name", "object_id", "description", "ip_address")
