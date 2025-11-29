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
    path("cars/search/", views.car_search, name="car_search"),
    path('search/', views.search_cars, name='search_cars'),

    # URL อื่นๆ ที่เกี่ยวกับรถและการจองจะอยู่ที่นี่
]