from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from .models import Board, BoardMember, Card
from .serializers import BoardSerializer, BoardCreateSerializer, CardSerializer


class BoardListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Board.objects.filter(
            board_members__user=self.request.user
        ).distinct().prefetch_related('board_members__user', 'lists__cards__assigned_to')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BoardCreateSerializer
        return BoardSerializer

    def perform_create(self, serializer):
        board = serializer.save(owner=self.request.user)
        BoardMember.objects.create(board=board, user=self.request.user, role='owner')


class BoardDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BoardSerializer

    def get_object(self):
        board = get_object_or_404(Board, pk=self.kwargs['pk'])
        if not board.board_members.filter(user=self.request.user).exists():
            self.permission_denied(self.request)
        return board


class CardDetailAPIView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CardSerializer

    def get_object(self):
        card = get_object_or_404(Card, pk=self.kwargs['pk'])
        board = card.list.board
        if not board.board_members.filter(user=self.request.user).exists():
            self.permission_denied(self.request)
        return card

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


class MyCardsAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CardSerializer

    def get_queryset(self):
        return Card.objects.filter(
            assigned_to=self.request.user
        ).select_related('list__board', 'assigned_to').order_by('due_date')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stats_api_view(request):
    user = request.user
    if not hasattr(user, 'profile') or not user.profile.is_superadmin:
        return Response({'error': 'Solo accesible para superadmins.'}, status=status.HTTP_403_FORBIDDEN)

    from django.contrib.auth.models import User
    data = {
        'total_usuarios': User.objects.count(),
        'usuarios_activos': User.objects.filter(is_active=True).count(),
        'total_tableros': Board.objects.count(),
        'total_tarjetas': Card.objects.count(),
        'tarjetas_por_estado': {
            'pendiente':   Card.objects.filter(status='pendiente').count(),
            'en_proceso':  Card.objects.filter(status='en_proceso').count(),
            'completado':  Card.objects.filter(status='completado').count(),
        },
    }
    return Response(data)
