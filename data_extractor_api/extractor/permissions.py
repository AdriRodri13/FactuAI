# permissions.py

from rest_framework.permissions import BasePermission
from .models import APIKey

class TieneAPIKey(BasePermission):
    def has_permission(self, request, view):
        clave = request.headers.get('X-API-KEY')
        if not clave:
            return False
        return APIKey.objects.filter(clave=clave, activa=True).exists()
