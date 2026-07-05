from rest_framework import serializers
from .models import Board, List, Card, BoardMember


class BoardMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = BoardMember
        fields = ['id', 'username', 'role']


class CardSerializer(serializers.ModelSerializer):
    assigned_to = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    list_title = serializers.CharField(source='list.title', read_only=True)
    board_id = serializers.IntegerField(source='list.board.id', read_only=True)

    class Meta:
        model = Card
        fields = ['id', 'title', 'description', 'status', 'due_date', 'assigned_to', 'list', 'list_title', 'board_id', 'position']
        read_only_fields = ['id', 'list_title', 'board_id', 'assigned_to']


class ListSerializer(serializers.ModelSerializer):
    cards = CardSerializer(many=True, read_only=True)

    class Meta:
        model = List
        fields = ['id', 'title', 'position', 'cards']


class BoardSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username', read_only=True)
    members = BoardMemberSerializer(source='board_members', many=True, read_only=True)
    lists = ListSerializer(many=True, read_only=True)

    class Meta:
        model = Board
        fields = ['id', 'title', 'description', 'background_color', 'is_chat_locked', 'owner', 'members', 'lists', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']


class BoardCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ['title', 'description', 'background_color']
