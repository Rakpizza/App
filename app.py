import streamlit as st
import pandas as pd
import easyocr
from PIL import Image
import numpy as np
import re
import io

# Set page config
st.set_page_config(
    page_title="DualAsset Analyzer Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
    <style>
    body { background-color: #0d1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 8px; }
    .highlight-buy { background-color: rgba(34, 197, 94, 0.2); padding: 15px; border-left: 4px solid #22c55e; border-radius: 4px; }
    .highlight-sell { background-color: rgba(239, 68, 68, 0.2); padding: 15px; border-left: 4px solid #ef4444; border-radius: 4px; }
    .highlight-hold { background-color: rgba(234, 179, 8, 0.2); padding: 15px; border-left: 4px solid #eab308; border-radius: 4px; }
    </style>
""", unsafe_allow_html=True)

# Title
st.title("📊 DualAsset Analyzer Pro")
st.markdown("**זיהוי אוטומטי של הצעות Bybit Dual Asset מתוך צילום מסך**")
st.divider()

# Initialize OCR reader
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en', 'he'], gpu=False)

reader = load_ocr()

def extract_numbers_from_text(text):
    """Extract numbers in various formats"""
    numbers = re.findall(r'\d+\.?\d*', text)
    return [float(n) for n in numbers]

def process_image(image):
    """Process image with OCR and extract data"""
    try:
        # Convert PIL image to numpy array
        img_array = np.array(image)
        
        # Run OCR
        results = reader.readtext(img_array, detail=0)
        
        return results
    except Exception as e:
        st.error(f"❌ שגיאה בעיבוד התמונה: {str(e)}")
        return None

def parse_ocr_results(ocr_text):
    """Parse OCR results into structured data"""
    offers = []
    
    # Join all text
    full_text = " ".join(ocr_text)
    
    # Find Index Price (usually appears once)
    index_match = re.search(r'Index[:\s]*(\d+\.?\d*)', full_text, re.IGNORECASE)
    index_price = float(index_match.group(1)) if index_match else None
    
    # Split text into lines for row processing
    lines = ocr_text
    
    current_offer = {}
    
    for line in lines:
        line_lower = line.lower()
        
        # Look for Target prices
        if 'target' in line_lower or re.search(r'\d+\.\d{1,4}', line):
            numbers = extract_numbers_from_text(line)
            if numbers:
                for num in numbers:
                    if current_offer:
                        offers.append(current_offer.copy())
                    current_offer = {'target': num}
        
        # Look for APR values
        if '%' in line or 'apr' in line_lower:
            numbers = extract_numbers_from_text(line)
            if numbers:
                current_offer['apr'] = numbers[0]
        
        # Look for Delta values
        if 'δ' in line_lower or '±' in line:
            numbers = extract_numbers_from_text(line)
            if numbers:
                current_offer['delta'] = numbers[0]
    
    if current_offer:
        offers.append(current_offer)
    
    # Remove duplicates and invalid entries
    valid_offers = []
    seen = set()
    
    for offer in offers:
        if 'target' in offer and 'apr' in offer:
            key = (offer['target'], offer['apr'])
            if key not in seen:
                seen.add(key)
                valid_offers.append(offer)
    
    return valid_offers, index_price

def calculate_delta(target, index):
    """Calculate delta percentage"""
    if not index or index == 0:
        return None
    return ((target - index) / index) * 100

def calculate_daily_profit(apr):
    """Calculate daily profit from APR"""
    return apr / 365

def classify_offer(delta, apr, price_distance_pct=None):
    """Classify offer as Buy/Sell/Hold"""
    if delta is None or apr is None:
        return "Hold", "🟨"
    
    # Sell High: positive delta, high APR
    if delta >= 0.3 and apr > 150:
        return "Sell High 📈", "🟩"
    
    # Buy Low: negative delta, high APR
    if delta <= -0.3 and apr > 150:
        return "Buy Low 📉", "🟩"
    
    # Between range but reasonable
    if -0.3 <= delta <= 0.3 and apr > 80:
        return "Split 💛", "🟨"
    
    # Too far or low APR
    if abs(delta) > 5:
        return "Skip ❌", "🟥"
    
    return "Hold 🔄", "🟨"

def create_dataframe(offers, index_price):
    """Create structured DataFrame from offers"""
    data = []
    
    for offer in offers:
        target = offer.get('target')
        apr = offer.get('apr', 0)
        delta = calculate_delta(target, index_price) if index_price else None
        daily_profit = calculate_daily_profit(apr)
        decision, emoji = classify_offer(delta, apr)
        
        data.append({
            'Target Price': f"${target:.2f}",
            'Index Price': f"${index_price:.2f}" if index_price else "N/A",
            'Δ %': f"{delta:.2f}%" if delta else "N/A",
            'APR': f"{apr:.1f}%",
            'Daily Profit': f"{daily_profit:.2f}%",
            'Decision': decision,
            'Emoji': emoji
        })
    
    return pd.DataFrame(data)

def get_top_recommendations(offers, index_price):
    """Get top Buy Low and Sell High offers"""
    buy_offers = []
    sell_offers = []
    
    for offer in offers:
        target = offer.get('target')
        apr = offer.get('apr', 0)
        delta = calculate_delta(target, index_price) if index_price else None
        
        if delta is not None:
            if delta <= -0.3 and apr > 150:
                buy_offers.append({
                    'target': target,
                    'apr': apr,
                    'delta': delta,
                    'score': apr * abs(delta)
                })
            elif delta >= 0.3 and apr > 150:
                sell_offers.append({
                    'target': target,
                    'apr': apr,
                    'delta': delta,
                    'score': apr * delta
                })
    
    best_buy = max(buy_offers, key=lambda x: x['score']) if buy_offers else None
    best_sell = max(sell_offers, key=lambda x: x['score']) if sell_offers else None
    
    return best_buy, best_sell

# Main UI
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📸 העלאת תמונה")
    uploaded_file = st.file_uploader(
        "בחר צילום מסך מ-Bybit Dual Asset",
        type=["jpg", "jpeg", "png"]
    )

with col2:
    st.subheader("ℹ️ הוראות שימוש")
    st.info("""
    1. צלם מסך מהאפליקציה של Bybit (Buy Low או Sell High)
    2. העלה את התמונה לעיל
    3. המערכת תזהה אוטומטית את כל ההצעות
    4. קבל המלצות מיידיות
    """)

if uploaded_file:
    st.divider()
    
    # Load and display image
    image = Image.open(uploaded_file)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("✅ התמונה שהועלתה")
        st.image(image, use_column_width=True)
    
    with col2:
        st.subheader("🔄 מעבד תמונה...")
        with st.spinner("⏳ מנתח את הנתונים..."):
            # Process image
            ocr_results = process_image(image)
            
            if ocr_results:
                offers, index_price = parse_ocr_results(ocr_results)
                
                if offers and index_price:
                    st.success(f"✅ נמצאו {len(offers)} הצעות!")
                    st.metric("📍 Index Price", f"${index_price:.2f}")
                else:
                    st.warning("⚠️ לא הצליח לזהות נתונים. נסה צילום מובחן יותר.")
    
    if offers and index_price:
        st.divider()
        
        # Create DataFrame
        df = create_dataframe(offers, index_price)
        
        # Display recommendations
        st.subheader("🎯 המלצות מובילות")
        
        best_buy, best_sell = get_top_recommendations(offers, index_price)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if best_buy:
                st.markdown("""
                <div class="highlight-buy">
                <h4>💰 הצעה לקנייה הטובה ביותר</h4>
                </div>
                """, unsafe_allow_html=True)
                st.metric("Target Price", f"${best_buy['target']:.4f}")
                st.metric("APR", f"{best_buy['apr']:.1f}%")
                st.metric("Δ", f"{best_buy['delta']:.2f}%")
            else:
                st.markdown("""
                <div class="highlight-hold">
                אין הצעות קנייה משתלמות כרגע
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if best_sell:
                st.markdown("""
                <div class="highlight-sell">
                <h4>💎 הצעה למכירה הטובה ביותר</h4>
                </div>
                """, unsafe_allow_html=True)
                st.metric("Target Price", f"${best_sell['target']:.4f}")
                st.metric("APR", f"{best_sell['apr']:.1f}%")
                st.metric("Δ", f"{best_sell['delta']:.2f}%")
            else:
                st.markdown("""
                <div class="highlight-hold">
                אין הצעות מכירה משתלמות כרגע
                </div>
                """, unsafe_allow_html=True)
        
        st.divider()
        
        # Display full table
        st.subheader("📋 כל ההצעות שזוהו")
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        
        # Download CSV
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 הורד נתונים ב-CSV",
            data=csv,
            file_name="dual_asset_analysis.csv",
            mime="text/csv"
        )

st.divider()
st.markdown("---")
st.markdown(
    "**מפתח על-ידי**: DualAsset Analyzer | "
    "**גרסה**: 1.0 | "
    "**OCR Engine**: EasyOCR"
)
