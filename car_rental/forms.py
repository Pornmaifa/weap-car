from django import forms
from .models import Car

class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        # ไม่ต้องใส่ owner และ status เพราะระบบจะเซ็ตอัตโนมัติใน view
        exclude = ['owner', 'status']
        widgets = {
            'car_type': forms.Select(attrs={'class': 'form-select'}),
            'service_type': forms.Select(attrs={'class': 'form-select'}),
            'country': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ประเทศ'}),
            'building_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ชื่ออาคาร (ถ้ามี)'}),
            'street_address': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ที่อยู่'}),
            'sub_district': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ตำบล/แขวง'}),
            'city': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'อำเภอ/เขต'}),
            'state': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'จังหวัด'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'รหัสไปรษณีย์'}),
            'brand': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ยี่ห้อรถ'}),
            'model': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'รุ่นรถ'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'รายละเอียดเพิ่มเติม'}),
            'price_per_day': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'ราคาเช่าต่อวัน'}),
            'unavailable_dates': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'วันที่ไม่ว่าง'}),
        }
