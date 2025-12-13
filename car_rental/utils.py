# car_rental/utils.py
from datetime import timedelta

def build_rental_context(car, pickup_datetime, dropoff_datetime):
    rental_days = (dropoff_datetime.date() - pickup_datetime.date()).days
    rental_days = max(rental_days, 1)

    total_price = rental_days * car.price_per_day  # ✅ แก้ตรงนี้

    return {
        "rental_days": rental_days,
        "total_price": total_price,
    }
