from django.db import models
from django.contrib.auth.models import User


class Board(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_boards')
    members = models.ManyToManyField(User, through='BoardMember', related_name='boards')
    background_color = models.CharField(max_length=7, default='#0079bf')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class BoardMember(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Propietario'),
        ('member', 'Miembro'),
    ]
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='board_members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['board', 'user']

    def __str__(self):
        return f'{self.user.username} - {self.board.title} ({self.role})'


class List(models.Model):
    title = models.CharField(max_length=200)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='lists')
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f'{self.title} ({self.board.title})'


class Card(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    list = models.ForeignKey(List, on_delete=models.CASCADE, related_name='cards')
    position = models.PositiveIntegerField(default=0)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_cards'
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return self.title
