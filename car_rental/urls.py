# car_rental/urls.py

# car_rental/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.car_list, name='car_list'),      # หน้ารายการรถ
    path('add/', views.add_car, name='add_car'),  
    path('add/preview/', views.add_car_preview, name='add_car_preview'),
    path('add/publish/<int:car_id>/', views.publish_car, name='publish_car'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('search/', views.search_cars, name='search_cars'),
    path('detail/<int:car_id>/', views.car_detail, name='car_detail'),
    path("review/<int:review_id>/reply/", views.submit_reply, name="submit_reply"),
    path('review/<int:review_id>/reply/', views.reply_to_car_review, name='reply_to_car_review'),
    path('renter-review/<int:review_id>/reply/', views.reply_to_owner_review, name='reply_to_owner_review'),
    path('owner-terms/', views.owner_terms_conditions, name='owner_terms'),
]