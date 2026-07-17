from django.db import models
from django.contrib.auth.models import User


class WorkGroup(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def is_admin(self, user):
        return self.group_members.filter(user=user, role='admin', status='approved').exists()

    def is_member(self, user):
        return self.group_members.filter(user=user, status='approved').exists()

    def has_pending(self, user):
        return self.group_members.filter(user=user, status='pending').exists()


class GroupMember(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('member', 'Miembro'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
    ]
    group = models.ForeignKey(WorkGroup, on_delete=models.CASCADE, related_name='group_members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['group', 'user']

    def __str__(self):
        return f'{self.user.username} - {self.group.name} ({self.role})'



class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=300)
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.title}'
