from django import forms
from .models import Car,BookingInspection

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


class InspectionForm(forms.ModelForm):
    class Meta:
        model = BookingInspection
        fields = ['image', 'description']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'w-full border rounded p-2', 'placeholder': 'เช่น รอยขีดข่วนประตูซ้าย'}),
            'image': forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'}),
        }
