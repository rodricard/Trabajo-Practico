from django.contrib import admin
from .models import Board, BoardMember, List, Card


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'owner__username']


@admin.register(BoardMember)
class BoardMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'board', 'role', 'joined_at']
    list_filter = ['role']


@admin.register(List)
class ListAdmin(admin.ModelAdmin):
    list_display = ['title', 'board', 'position']
    list_filter = ['board']


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ['title', 'list', 'assigned_to', 'due_date']
    list_filter = ['due_date', 'list__board']
    search_fields = ['title', 'assigned_to__username']
