from django.urls import path
from . import views

urlpatterns = [
    path('', views.board_list, name='board_list'),
    path('create/', views.board_create, name='board_create'),
    path('<int:pk>/', views.board_detail, name='board_detail'),
    path('<int:pk>/edit/', views.board_update, name='board_update'),
    path('<int:pk>/delete/', views.board_delete, name='board_delete'),
    path('<int:pk>/members/', views.board_members, name='board_members'),
    path('<int:board_pk>/members/<int:member_pk>/remove/', views.board_member_remove, name='board_member_remove'),
    path('<int:board_pk>/members/<int:member_pk>/set-role/', views.api_member_set_role, name='api_member_set_role'),
    path('<int:board_pk>/lists/create/', views.list_create, name='list_create'),
    path('lists/<int:pk>/delete/', views.list_delete, name='list_delete'),
    path('lists/<int:list_pk>/cards/create/', views.card_create, name='card_create'),
    path('cards/<int:pk>/', views.card_detail, name='card_detail'),
    path('cards/<int:pk>/delete/', views.card_delete, name='card_delete'),
]
