import streamlit as st
from PIL import Image
import easyocr
import re
import pandas as pd
import numpy as np
import io
import time

# ----------------------------------------
# ⚙️ הגדרות כלליות
# ----------------------------------------
st.set_page_config(page_title="DualAsset Analyzer Pro", layout="centered")

st.title("📊 DualAsset Analyzer Pro")
st.write("העלה צילום מסך מ־Bybit (Buy Low / Sell High) — המערכת תזהה אוטומטית את הנתונים ותציג את ההמלצה הטובה ביותר.")
st.divider()

# ----------------------------------------
# 📸 העלאת תמונה
# ----------------------------------------
uploaded_files = st.file_uploader("בחר תמונה או כמה תמונות לניתוח", accept_multiple_files=True, type=["png", "jpg", "jpeg"])

if not uploaded_files:
    st.info("📷 העלה צילום מסך אחד לפחות כדי להתחיל.")
    st.stop()

# ----------------------------------------
# ⏳ טוען...
# ----------------------------------------
with st.spinner("🔍 קורא ומנתח את הנתונים מהתמונות... אנא המתן מספר שניות"):
    reader = easyocr.Reader(['en'])
    time.sleep(1)

    data_rows = []

    for file in uploaded_files:
        img = Image.open(file)
        result = reader.readtext(np.array(img))
        text = " ".join([r[1] for r in result])

        # איתור Index Price
        index_match = re.search(r"Index Price.?([0-9]+\.[0-9]+)", text)
        index_price = float(index_match.group(1)) if index_match else None

        # איתור ערכים של Target Price ו־APR
        lines = text.split()
        for i in range(len(lines) - 2):
            if re.match(r"^[0-9]+\.[0-9]+$", lines[i]) and "%" in lines[i+2]:
                try:
                    target = float(lines[i])
                    apr = float(lines[i+2].replace("%", ""))
                    data_rows.append({
                        "תמונה": file.name,
                        "Index Price": index_price,
                        "Target": target,
                        "APR": apr
                    })
                except:
                    continue

# ----------------------------------------
# 🧾 בדיקה אם נמצאו נתונים
# ----------------------------------------
if not data_rows:
    st.error("❌ לא זוהו נתונים. ודא שהתמונה מכילה טבלת Bybit עם Index / Target / APR.")
    st.stop()

df = pd.DataFrame(data_rows)

# אם לא זוהה מחיר אינדקס – נחשב ממוצע
if df["Index Price"].isna().any():
    df["Index Price"].fillna(df["Target"].mean(), inplace=True)

# ----------------------------------------
# 📊 חישוב סטיות והמלצות
# ----------------------------------------
def analyze(row):
    diff = ((row["Target"] - row["Index Price"]) / row["Index Price"]) * 100
    daily_yield = row["APR"] / 365
    if abs(diff) < 0.3:
        decision = "⚖️ פצל (Too close)"
    elif diff > 0.3 and row["APR"] > 150:
        decision = "📈 Sell High"
    elif diff < -0.3 and row["APR"] > 150:
        decision = "📉 Buy Low"
    else:
        decision = "🚫 לא משתלם"
    return pd.Series({"Δ %": round(diff, 3), "החלטה": decision})

analyzed = df.apply(analyze, axis=1)
final = pd.concat([df, analyzed], axis=1)

# ----------------------------------------
# 🧠 מציאת ההצעה הטובה ביותר
# ----------------------------------------
buy_best = final[final["החלטה"].str.contains("Buy Low", na=False)].sort_values("APR", ascending=False).head(1)
sell_best = final[final["החלטה"].str.contains("Sell High", na=False)].sort_values("APR", ascending=False).head(1)

# ----------------------------------------
# 📊 הצגת טבלה
# ----------------------------------------
st.success("✅ הניתוח הושלם!")
st.dataframe(final, use_container_width=True)

# ----------------------------------------
# 🏆 המלצה סופית
# ----------------------------------------
st.divider()
if not buy_best.empty or not sell_best.empty:
    st.subheader("💡 ההצעות החזקות ביותר:")
    if not buy_best.empty:
        st.write(f"**קנייה (Buy Low):** Target {buy_best.iloc[0]['Target']} | APR {buy_best.iloc[0]['APR']}% | Δ {buy_best.iloc[0]['Δ %']}%")
    if not sell_best.empty:
        st.write(f"**מכירה (Sell High):** Target {sell_best.iloc[0]['Target']} | APR {sell_best.iloc[0]['APR']}% | Δ {sell_best.iloc[0]['Δ %']}%")
else:
    st.info("לא נמצאה הזדמנות יוצאת דופן כרגע. ייתכן שהשוק יציב מדי.")

# ----------------------------------------
# 📥 הורדת תוצאות
# ----------------------------------------
st.download_button(
    "⬇️ הורד תוצאות כ־CSV",
    data=final.to_csv(index=False).encode('utf-8'),
    file_name="dualasset_analysis.csv",
    mime="text/csv"
)

st.caption("נבנה על ידי Itamar & ChatGPT — גרסה 2.0 (Auto Detection + EasyOCR)")
