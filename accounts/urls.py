from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import LoginForm

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        authentication_form=LoginForm,
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    # Superadmin
    path('superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('superadmin/boards/', views.superadmin_boards, name='superadmin_boards'),
    path('superadmin/stats/', views.api_superadmin_stats, name='api_superadmin_stats'),
    path('superadmin/users/<int:user_id>/toggle-active/', views.api_toggle_user_active, name='api_toggle_user_active'),
    path('superadmin/users/<int:user_id>/toggle-superadmin/', views.superadmin_toggle_superadmin, name='superadmin_toggle_superadmin'),
]
