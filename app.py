import streamlit as st
import easyocr
import pandas as pd
import numpy as np
from PIL import Image
import re
from datetime import datetime

st.set_page_config(
    page_title="DualAsset Analyzer Pro",
    page_icon="📊",
    layout="wide",
)

st.title("📊 DualAsset Analyzer Pro")
st.subheader("🎯 זיהוי אוטומטי של הצעות Bybit הכי רווחיות")

# ===== יצירת OCR Reader =====
@st.cache_resource
def load_ocr():
    st.write("Loading OCR Engine...")
    return easyocr.Reader(['en'], gpu=False)

try:
    reader = load_ocr()
    st.write("OCR loaded successfully")
except Exception as e:
    st.error(f"OCR Error: {e}")
    reader = None

# ===== פונקציות =====

def extract_ocr_text(image):
    """קריאת טקסט מהתמונה"""
    if reader is None:
        st.error("OCR not available")
        return None
    
    try:
        img_array = np.array(image)
        results = reader.readtext(img_array, detail=0)
        return results
    except Exception as e:
        st.error(f"OCR Error: {str(e)}")
        return None

def parse_numbers_from_text(text):
    """חילוץ מספרים מטקסט"""
    # מוצא מספרים עם נקודה או פסיק
    numbers = re.findall(r'[\d,]+\.?\d*', text)
    result = []
    for n in numbers:
        try:
            result.append(float(n.replace(',', '')))
        except:
            pass
    return result

def analyze_ocr_results(ocr_text_list):
    """ניתוח תוצאות OCR"""
    
    all_text = '\n'.join(ocr_text_list)
    
    st.write("📄 **טקסט שקרא:**")
    st.text(all_text[:500])  # הצגת ראשית
    
    # חיפוש מחיר Index
    index_price = None
    for line in ocr_text_list:
        if 'index' in line.lower() or 'mark' in line.lower():
            nums = parse_numbers_from_text(line)
            if nums:
                index_price = nums[0]
                break
    
    if not index_price:
        # ננסה את השורה הראשונה
        nums = parse_numbers_from_text(ocr_text_list[0])
        if nums and nums[0] > 100:
            index_price = nums[0]
    
    st.write(f"🔍 Index Price שנמצא: **${index_price}**")
    
    # חיפוש כל המספרים
    all_numbers = parse_numbers_from_text(all_text)
    
    st.write(f"📊 סה"כ מספרים שנמצאו: {len(all_numbers)}")
    st.write(f"📝 הנתונים: {all_numbers[:20]}")  # הראשונים 20
    
    # הפרדה ל־prices ו־APR
    prices = []
    apr_values = []
    
    for num in all_numbers:
        if num > 1000 or (num > 100 and index_price and abs(num - index_price) < 10000):
            if num not in prices:
                prices.append(num)
        elif num >= 50 and num <= 500:  # APR בטווח סביר
            if num not in apr_values:
                apr_values.append(num)
    
    return index_price, prices, apr_values

def detect_type(all_text):
    """זיהוי Buy Low או Sell High"""
    if 'sell' in all_text.lower():
        return 'Sell High'
    elif 'buy' in all_text.lower():
        return 'Buy Low'
    return 'Unknown'

# ===== ממשק =====

st.markdown("---")

uploaded_file = st.file_uploader(
    "📸 העלו צילום מסך של Dual Asset",
    type=['jpg', 'jpeg', 'png']
)

if uploaded_file:
    # הצגת התמונה
    image = Image.open(uploaded_file)
    st.image(image, caption="התמונה שהועלתה", width=400)
    
    st.write("⏳ **מעבדים...**")
    
    # קריאת OCR
    ocr_results = extract_ocr_text(image)
    
    if ocr_results:
        st.success("✅ OCR קרא את התמונה!")
        
        # ניתוח
        index_price, prices, apr_values = analyze_ocr_results(ocr_results)
        
        # זיהוי סוג
        all_text = '\n'.join(ocr_results)
        table_type = detect_type(all_text)
        
        st.info(f"🏷️ **סוג:** {table_type}")
        
        if index_price and prices and apr_values:
            st.success("✅ נתונים מלאים!")
            
            # יצירת הצעות
            offers = []
            for p in prices[:10]:  # עד 10 הצעות
                for a in apr_values[:5]:  # עד 5 APR ערכים
                    delta = ((p - index_price) / index_price) * 100
                    daily = a / 365
                    score = a * abs(delta)
                    
                    offers.append({
                        'Target': p,
                        'APR': a,
                        'Delta': delta,
                        'Daily': daily,
                        'Score': score
                    })
            
            # מיון לפי Score
            offers = sorted(offers, key=lambda x: x['Score'], reverse=True)
            
            # הצגה
            st.subheader("📊 Top Offers:")
            df = pd.DataFrame(offers[:5])
            st.dataframe(df, use_container_width=True)
            
            # המלצה
            best = offers[0]
            
            st.markdown(f"""
## 🎯 **ההמלצה המובילה:**

- **סוג:** {table_type}
- **Index:** ${index_price:.2f}
- **Target:** ${best['Target']:.2f}
- **Delta:** {best['Delta']:.3f}%
- **APR:** {best['APR']:.2f}%
- **Daily Profit:** {best['Daily']:.3f}%
- **Score:** {best['Score']:.2f}

✅ **זו ההצעה הטובה ביותר להשקעה!**
            """)
            
            # CSV
            csv = pd.DataFrame(offers).to_csv(index=False)
            st.download_button(
                "📥 הורד CSV",
                csv,
                file_name=f"offers_{datetime.now().strftime('%Y%m%d')}.csv"
            )
        
        else:
            st.error(f"""
❌ **בעיה בחילוץ נתונים:**
- Index: {index_price}
- Prices found: {len(prices)}
- APR values found: {len(apr_values)}

💡 ודקו שהתמונה כוללת מחיר Index ויעדים עם APR
            """)
    
    else:
        st.error("❌ OCR כשל - נסו תמונה אחרת")

else:
    st.info("👈 בחרו קובץ תמונה בשביל להתחיל")
