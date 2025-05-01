import secrets
from django.db import models

class APIKey(models.Model):
    nombre = models.CharField(max_length=100, unique=True)  # ← aquí está el cambio
    clave = models.CharField(max_length=40, unique=True, editable=False)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.clave:
            self.clave = secrets.token_hex(20)  # 40 caracteres seguros
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({'activa' if self.activa else 'inactiva'})"
