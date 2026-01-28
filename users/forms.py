# users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from car_rental.models import Profile 
from django.utils.translation import gettext_lazy as _  # ✅ 1. เพิ่มบรรทัดนี้สำคัญมาก!

# --- 1. ฟอร์มสำหรับหน้า "สมัครสมาชิก" (Register) ---
class UserRegisterForm(UserCreationForm):
    # ✅ 2. ใส่ _(...) ครอบข้อความภาษาไทยทั้งหมด
    first_name = forms.CharField(label=_('ชื่อจริง'), max_length=100)
    last_name = forms.CharField(label=_('นามสกุล'), max_length=100)
    email = forms.EmailField(label=_('อีเมล (ใช้เป็นชื่อผู้ใช้สำหรับเข้าสู่ระบบ)'), required=True)
    phone = forms.CharField(label=_('เบอร์โทรศัพท์'), max_length=20, required=True)
    license_no = forms.CharField(label=_('เลขที่ใบขับขี่'), max_length=50, required=True)
    image = forms.ImageField(label=_('รูปโปรไฟล์ (ไม่บังคับ)'), required=False)
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['image','email', 'first_name', 'last_name', 'phone', 'license_no' ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            # ✅ 3. แปล Error Message ด้วย
            raise forms.ValidationError(_("อีเมลนี้มีผู้ใช้งานแล้ว กรุณาใช้อีเมลอื่น"))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']
        
        if commit:
            user.save()
        return user

# --- 2. ฟอร์มสำหรับอัปเดต "User" (หน้าโปรไฟล์) ---
class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(label=_('อีเมล')) # ✅ แปล

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = { # ✅ เพิ่ม labels ตรงนี้เพื่อให้แปลชื่อ/นามสกุลในหน้า Edit Profile ได้
            'first_name': _('ชื่อจริง'),
            'last_name': _('นามสกุล'),
        }

# --- 3. ฟอร์มสำหรับอัปเดต "Profile" (หน้าโปรไฟล์) ---
class ProfileUpdateForm(forms.ModelForm):
    
    class Meta:
        model = Profile
        fields = ['image', 'phone', 'license_no']
        
        # ✅ 4. แปล Labels ใน Meta
        labels = {
            'image': _('รูปโปรไฟล์'),
            'phone': _('เบอร์โทรศัพท์'),
            'license_no': _('เลขที่ใบขับขี่'),
        }
        widgets = {
            'image': forms.FileInput, 
        }