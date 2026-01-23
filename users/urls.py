# users/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views

from car_rental import views
from . import views as user_views

urlpatterns = [
    path('register/', user_views.register, name='register'),
    path('profile/', user_views.profile, name='profile'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='users/logout.html'), name='logout'),
    path('become-owner/', user_views.become_owner, name='become_owner'),
    path('profile/view/<int:user_id>/', user_views.public_profile, name='public_profile'),
    path('login-redirect/', user_views.custom_login_redirect, name='login_redirect'),
    path('change-password/', user_views.change_password, name='change_password'),
]