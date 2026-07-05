from django.urls import path
from . import api_views

urlpatterns = [
    path('boards/', api_views.BoardListCreateAPIView.as_view(), name='api_boards'),
    path('boards/<int:pk>/', api_views.BoardDetailAPIView.as_view(), name='api_board_detail'),
    path('cards/', api_views.MyCardsAPIView.as_view(), name='api_my_cards'),
    path('cards/<int:pk>/', api_views.CardDetailAPIView.as_view(), name='api_card_detail'),
    path('stats/', api_views.stats_api_view, name='api_stats'),
]
