from django.contrib import admin
from .models import WorkGroup, GroupMember, Notification


@admin.register(WorkGroup)
class WorkGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'created_at']
    search_fields = ['name', 'created_by__username']


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'role', 'status', 'joined_at']
    list_filter = ['role', 'status']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'is_read', 'created_at']
    list_filter = ['is_read']
