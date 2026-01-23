# booking/forms.py
from django import forms
from car_rental.models import Booking

class RefundForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['refund_bank_name', 'refund_account_no', 'refund_account_name']
        labels = {
            'refund_bank_name': 'ธนาคาร',
            'refund_account_no': 'เลขที่บัญชี',
            'refund_account_name': 'ชื่อบัญชี',
        }