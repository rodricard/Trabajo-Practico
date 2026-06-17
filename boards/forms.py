from django import forms
from .models import Board, List, Card, BoardMessage


class BoardForm(forms.ModelForm):
    class Meta:
        model = Board
        fields = ['title', 'description', 'background_color']
        labels = {
            'title': 'Título',
            'description': 'Descripción',
            'background_color': 'Color de fondo',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción opcional...'}),
            'background_color': forms.TextInput(attrs={'type': 'color'}),
            'title': forms.TextInput(attrs={'placeholder': 'Nombre del tablero'}),
        }


class ListForm(forms.ModelForm):
    class Meta:
        model = List
        fields = ['title']
        labels = {'title': ''}
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Nombre de la lista', 'class': 'input-inline'}),
        }


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['title', 'description', 'due_date', 'assigned_to', 'list']
        labels = {
            'title': 'Título',
            'description': 'Descripción',
            'due_date': 'Fecha límite',
            'assigned_to': 'Asignado a',
            'list': 'Lista',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Título de la tarjeta'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Añade una descripción...'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }


class CardQuickForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['title']
        labels = {'title': ''}
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Título de la tarjeta', 'class': 'input-inline'}),
        }


class BoardMemberForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label='Nombre de usuario',
        widget=forms.TextInput(attrs={'placeholder': 'Buscar usuario...'}),
    )


class BoardMessageForm(forms.ModelForm):
    class Meta:
        model = BoardMessage
        fields = ['content']
        labels = {'content': ''}
        widgets = {
            'content': forms.TextInput(attrs={'placeholder': 'Escribí un mensaje...', 'autocomplete': 'off'}),
        }
