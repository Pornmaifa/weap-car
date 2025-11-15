# car_rental/urls.py

# car_rental/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.car_list, name='car_list'),      # หน้ารายการรถ
    path('add/step1/', views.add_car_step1, name='add_car_step1'),    # หน้าเพิ่มรถ
    path('add/step2/', views.add_car_step2, name='add_car_step2'), 
    path('add/step3/', views.add_car_step3, name='add_car_step3'),
    path('add/step4/', views.add_car_step4, name='add_car_step4'),
    path('add/step5/', views.add_car_step5, name='add_car_step5'),
    path('add/step6/', views.add_car_step6, name='add_car_step6'),
    path('add/step7/', views.add_car_step7, name='add_car_step7'),
    path('add/preview/<int:car_id>/', views.add_car_preview, name='add_car_preview'),
    path('add/publish/<int:car_id>/', views.publish_car, name='publish_car'),
    # URL อื่นๆ ที่เกี่ยวกับรถและการจองจะอยู่ที่นี่
]