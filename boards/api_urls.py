from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import api_views
from groups import api_views as group_api_views

urlpatterns = [
    path('token/', obtain_auth_token, name='api_token'),
    path('boards/', api_views.BoardListCreateAPIView.as_view(), name='api_boards'),
    path('boards/<int:pk>/', api_views.BoardDetailAPIView.as_view(), name='api_board_detail'),
    path('cards/', api_views.MyCardsAPIView.as_view(), name='api_my_cards'),
    path('cards/<int:pk>/', api_views.CardDetailAPIView.as_view(), name='api_card_detail'),
    path('stats/', api_views.stats_api_view, name='api_stats'),
    path('groups/', group_api_views.GroupListAPIView.as_view(), name='api_groups'),
    path('notifications/', group_api_views.NotificationListAPIView.as_view(), name='api_notifications'),
]
