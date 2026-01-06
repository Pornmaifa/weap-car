# linebot/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # ลิงก์จะเป็น: /linebot/webhook/
    path('webhook/', views.callback, name='callback'),
]