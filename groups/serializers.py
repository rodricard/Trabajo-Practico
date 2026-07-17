from rest_framework import serializers
from .models import WorkGroup, GroupMember, Notification


class GroupMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = GroupMember
        fields = ['id', 'username', 'role', 'status']


class WorkGroupSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    members = GroupMemberSerializer(source='group_members', many=True, read_only=True)

    class Meta:
        model = WorkGroup
        fields = ['id', 'name', 'description', 'created_by', 'members', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'link', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']
