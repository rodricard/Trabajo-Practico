from django.urls import path
from . import views

urlpatterns = [
    path('', views.group_list, name='group_list'),
    path('crear/', views.group_create, name='group_create'),
    path('<int:pk>/', views.group_detail, name='group_detail'),
    path('<int:pk>/unirse/', views.group_join, name='group_join'),
    path('<int:pk>/miembros/<int:member_pk>/aprobar/', views.group_approve, name='group_approve'),
    path('<int:pk>/miembros/<int:member_pk>/rechazar/', views.group_reject, name='group_reject'),
    path('<int:pk>/miembros/<int:member_pk>/expulsar/', views.group_remove_member, name='group_remove_member'),
    path('<int:pk>/miembros/<int:member_pk>/rol/', views.group_set_role, name='group_set_role'),
    path('notificaciones/', views.notifications_list, name='notifications_list'),
]
