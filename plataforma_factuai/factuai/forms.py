from django import forms
from .models import Empresa

class UploadFileForm(forms.Form):
    """Formulario vacío solo para CSRF"""
    pass

from django import forms
from .models import Empresa

class EmpresaForm(forms.ModelForm):
    """Formulario para crear y editar empresas"""
    
    class Meta:
        model = Empresa
        fields = ['nombre', 'nif', 'direccion', 'telefono', 'email']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la empresa'}),
            'nif': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIF de la empresa'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono de contacto'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email de contacto'}),
        }
        error_messages = {
            'nombre': {
                'required': 'El nombre de la empresa es obligatorio',
                'unique': 'Ya existe una empresa con este nombre'
            }
        }