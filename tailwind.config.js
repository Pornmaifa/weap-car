/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    // 1. Path สำหรับ Templates ที่ระดับราก (โฟลเดอร์ 'templates' โดยตรง)
    "./templates/**/*.html", 
    
    // 2. Path สำหรับ Templates ภายในแอป (เช่น users/templates/users/...)
    //    Path นี้จะครอบคลุมทุกโฟลเดอร์ที่ไม่ได้อยู่ที่ระดับราก (เช่น users, car_rental)
    "./*/templates/**/*.html", 

    // 3. Path สำหรับไฟล์ JS (เผื่อใช้คลาสในโค้ด JS)
    "./**/*.js", 
  ],
  theme: {
    extend: {
        // เพิ่มสีที่คุณกำหนดเองลงในธีมได้
        colors: {
          'primary-car': '#48a9b9',
        },
    },
  },
  plugins: [],
}