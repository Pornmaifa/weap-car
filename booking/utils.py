import binascii

def crc16(data: bytes):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if (crc & 0x8000):
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
    return crc & 0xFFFF

def format_field(id, value):
    return '{:02}{:02}{}'.format(id, len(value), value)

def generate_promptpay_payload(id_or_phone, amount=None):
    # 1. จัดการเบอร์โทรหรือเลขบัตร
    target = id_or_phone.replace('-', '').replace(' ', '')
    
    # 2. ตรวจสอบประเภท
    if len(target) >= 13: # บัตรประชาชน
        target_type = '02' 
    else: # เบอร์โทรศัพท์
        target_type = '01' 
        if target.startswith('0'):
            target = '66' + target[1:] # เปลี่ยน 08x เป็น 668x
    
    # 3. สร้างข้อมูล Payload
    data = [
        format_field(0, '01'),
        format_field(1, '12' if amount else '11'),
        format_field(29, 
            format_field(0, 'A000000677010111') +
            format_field(1, format_field(target_type, target))
        ),
        format_field(58, 'TH'),
        format_field(53, '764'),
    ]

    if amount:
        amount_str = '{:.2f}'.format(float(amount))
        data.append(format_field(54, amount_str))

    raw_data = ''.join(data) + '6304'
    crc_val = crc16(raw_data.encode())
    return raw_data + '{:04X}'.format(crc_val)