# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from car_rental.models import Profile # (ต้อง import Profile Model ของคุณ)


# --- 1. ฟอร์มสำหรับหน้า "สมัครสมาชิก" (Register) ---
# (อันนี้เหมือนเดิม ไม่ต้องแก้)
class UserRegisterForm(UserCreationForm):
    first_name = forms.CharField(label='ชื่อจริง', max_length=100)
    last_name = forms.CharField(label='นามสกุล', max_length=100)
    email = forms.EmailField(label='อีเมล')
    image = forms.ImageField(label='รูปโปรไฟล์ (ไม่บังคับ)', required=False)
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']

    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        self.fields['username'].label = "เบอร์โทรศัพท์ (ใช้เป็น Username)"


# --- 2. ฟอร์มสำหรับอัปเดต "User" (หน้าโปรไฟล์) ---
# (นี่คือ u_form ที่ View ของเราต้องการ)
class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(label='อีเมล')

    class Meta:
        model = User
        # (แก้ไข!) เราจะอัปเดต username (เบอร์โทร) ที่นี่
        fields = ['first_name', 'last_name', 'email', 'username']

    def __init__(self, *args, **kwargs):
        # (เพิ่ม!) ตั้งชื่อ 'username' เป็น 'เบอร์โทร'
        super(UserUpdateForm, self).__init__(*args, **kwargs)
        self.fields['username'].label = "เบอร์โทรศัพท์"


# --- 3. ฟอร์มสำหรับอัปเดต "Profile" (หน้าโปรไฟล์) ---
# (นี่คือ p_form ที่ View ของเราต้องการ)
class ProfileUpdateForm(forms.ModelForm):
    
    class Meta:
        model = Profile
        # (แก้ไข!) เอา 'phone_number' (ที่ไม่มีอยู่จริง) ออก
        # เหลือแค่ 'image'
        fields = ['image'] 
        
        labels = {
            'image': 'เปลี่ยนรูปโปรไฟล์',
        }
        widgets = {
            'image': forms.FileInput, 
        }