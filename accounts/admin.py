from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_superadmin']
    list_filter = ['is_superadmin']
    search_fields = ['user__username']
