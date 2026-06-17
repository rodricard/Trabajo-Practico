from django import forms
from .models import WorkGroup


class WorkGroupForm(forms.ModelForm):
    class Meta:
        model = WorkGroup
        fields = ['name', 'description']
        labels = {
            'name': 'Nombre del grupo',
            'description': 'Descripción',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nombre del grupo'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción opcional...'}),
        }
