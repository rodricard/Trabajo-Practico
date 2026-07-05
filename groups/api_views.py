from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import WorkGroup, Notification
from .serializers import WorkGroupSerializer, NotificationSerializer


class GroupListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkGroupSerializer

    def get_queryset(self):
        return WorkGroup.objects.filter(
            group_members__user=self.request.user,
            group_members__status='approved'
        ).distinct()


class NotificationListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
