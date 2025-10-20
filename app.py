import streamlit as st
from PIL import Image
import easyocr
import re
import pandas as pd

# -----------------------------
# ⚙️ הגדרות כלליות
# -----------------------------
st.set_page_config(page_title="DualAsset Analyzer Pro", layout="centered")

st.title("📊 DualAsset Analyzer Pro")
st.write("העלה צילום מסך מ־Bybit (Buy Low / Sell High) — המערכת תנתח אוטומטית את ההצעות ותציג את ההמלצות הטובות ביותר.")
st.divider()

# -----------------------------
# 📸 העלאת תמונה
# -----------------------------
uploaded_files = st.file_uploader("בחר תמונה או כמה תמונות לניתוח", accept_multiple_files=True, type=["png", "jpg", "jpeg"])

if not uploaded_files:
    st.info("📷 העלה צילום מסך אחד לפחות כדי להתחיל.")
    st.stop()

# -----------------------------
# 🧠 קריאת טקסט מהתמונה (EasyOCR)
# -----------------------------
reader = easyocr.Reader(['en'])
data_rows = []

for file in uploaded_files:
    img = Image.open(file)
    result = reader.readtext(img)
    text = " ".join([res[1] for res in result])

    # זיהוי המטבע
    coin_match = re.search(r"(BTC|ETH|BNB|ARB|SOL|ADA|DOGE|MNT|USDT)", text)
    coin = coin_match.group(1) if coin_match else "לא זוהה"

    # חיפוש Target ו־APR
    lines = text.split()
    for i, word in enumerate(lines):
        if re.match(r"^\d{3,5}\.\d+$", word):
            if i + 1 < len(lines) and re.match(r"^\d{2,4}\.?\d*%$", lines[i + 1]):
                target_val = float(word)
                apr = float(lines[i + 1].replace("%", ""))
                data_rows.append({"מטבע": coin, "Target": target_val, "APR": apr})

# -----------------------------
# בדיקה אם נמצאו נתונים
# -----------------------------
if not data_rows:
    st.warning("❌ לא נמצאו נתונים בתמונה. נסה צילום ממוקד של טבלת Bybit בלבד.")
    st.stop()

df = pd.DataFrame(data_rows)

# -----------------------------
# 💰 הזנת מחיר נוכחי וסכום השקעה
# -----------------------------
st.divider()
current_price = st.number_input("💲 מחיר נוכחי של המטבע", min_value=0.0, value=float(df['Target'].mean()), step=0.0001)
investment = st.number_input("💵 סכום השקעה (USDT)", min_value=1.0, value=50.0, step=1.0)

# -----------------------------
# 📊 חישוב דלתא והמלצות
# -----------------------------
def analyze_row(row):
    delta = ((row['Target'] - current_price) / current_price) * 100
    apr = row['APR']
    daily_yield = investment * (apr / 100 / 365)

    if abs(delta) < 1:
        decision = "Hold / Split"
        color = "🟨"
    elif delta <= -1 and apr > 150:
        decision = "Buy Low"
        color = "🟩"
    elif delta >= 1 and apr > 150:
        decision = "Sell High"
        color = "🟩"
    elif abs(delta) > 5:
        decision = "Skip (Too far)"
        color = "🟥"
    else:
        decision = "Hold"
        color = "🟨"

    return pd.Series({
        "Δ %": round(delta, 2),
        "APR %": apr,
        "רווח יומי (USDT)": round(daily_yield, 3),
        "המלצה": f"{color} {decision}"
    })

result = df.apply(analyze_row, axis=1)
final_df = pd.concat([df, result], axis=1)

# -----------------------------
# 🧾 תוצאות
# -----------------------------
st.divider()
st.subheader("🔍 תוצאות הניתוח:")
st.dataframe(final_df, use_container_width=True)

best = final_df[final_df["המלצה"].str.contains("Buy Low|Sell High")]
if not best.empty:
    st.success("✅ הצעות מומלצות:\n" + "\n".join(
        f"{row['מטבע']} @ {row['Target']} → {row['המלצה']} (APR {row['APR %']}%)"
        for _, row in best.iterrows()
    ))
else:
    st.info("אין כרגע הצעות חזקות מספיק — רוב ההצעות קרובות מדי או רחוקות מדי.")

st.download_button("⬇️ הורד טבלה (CSV)", data=final_df.to_csv(index=False).encode('utf-8'), file_name="dualasset_results.csv", mime="text/csv")
st.divider()
st.caption("נבנה על ידי ChatGPT & Itamar 🔹 גרסה 1.1 עם EasyOCR")
