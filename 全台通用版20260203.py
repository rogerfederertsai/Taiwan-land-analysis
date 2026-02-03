import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import folium
import geopandas as gpd
from streamlit_folium import st_folium
import os
import io

# 1. 網頁基本設定
st.set_page_config(page_title="全台實價登錄分析系統", layout="wide")

# --- 2. 字體與路徑處理 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
font_path = os.path.join(BASE_DIR, 'NotoSansTC-Regular.ttf')
geojson_path = os.path.join(BASE_DIR, 'information', 'TOWN_MOI_1140318.json')

if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
else:
    st.sidebar.error("❌ 找不到字體檔，統計圖可能無法顯示中文")
    font_prop = None

plt.rcParams['axes.unicode_minus'] = False

# 下載圖片輔助函式
def get_image_download(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', dpi=300)
    buf.seek(0)
    return buf

# --- 3. 核心邏輯 ---
st.title("🏙️ 全台實價登錄分析系統")

uploaded_file = st.sidebar.file_uploader("請上傳內政部資料 (Excel 或 CSV)", type=['xls', 'xlsx', 'csv'])

if uploaded_file:
    try:
        # 自動判定檔案格式讀取
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            # Excel 通常包含內政部定義檔，跳過第二行
            df = pd.read_excel(uploaded_file, sheet_name=0, skiprows=[1])
        
        # 欄位自動偵測
        area_col = next((c for c in df.columns if any(k in str(c) for k in ['鄉鎮市區', '行政區'])), None)
        addr_col = next((c for c in df.columns if any(k in str(c) for k in ['土地位置', '建物門牌'])), None)
        price_col = next((c for c in df.columns if any(k in str(c) for k in ['總價元'])), None)

        if area_col:
            # 偵測縣市
            detect_text = "".join(df[addr_col].dropna().astype(str).head(20)) + uploaded_file.name
            current_city = "臺南市"
            all_cities = ["臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "嘉義市", "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"]
            for city in all_cities:
                if city in detect_text or city.replace("臺", "台") in detect_text:
                    current_city = city
                    break
            
            target_city_tai = current_city.replace("台", "臺")
            target_city_ta = current_city.replace("臺", "台")
            
            # 清理行政區名稱 (移除縣市前綴)
            df['Clean_Area'] = df[area_col].astype(str).str.replace(f"^{target_city_tai}|^{target_city_ta}", "", regex=True).str.strip()
            total_count = len(df)
            all_counts = df['Clean_Area'].value_counts()
            top_10 = all_counts.head(10)

            # --- 第一部分：成交量分析圖表 ---
            st.subheader("📊 成交量分佈分析")
            c1, c2 = st.columns(2)
            
            with c1:
                title1 = st.text_input("成交排行標題", f"🏆 {current_city}成交量前十名行政區")
                fig1, ax1 = plt.subplots(figsize=(10, 7))
                sns.barplot(x=top_10.values, y=top_10.index, hue=top_10.index, palette='viridis', ax=ax1, legend=False)
                ax1.set_title(title1, fontproperties=font_prop, fontsize=16)
                for i, v in enumerate(top_10.values):
                    ax1.text(v, i, f' {int(v)}筆', va='center', fontproperties=font_prop)
                st.pyplot(fig1)
                st.download_button("📥 下載排行圖", get_image_download(fig1), f"{current_city}_排行.png", "image/png")

            with c2:
                title2 = st.text_input("成交比例標題", f"📈 {current_city}成交比例")
                fig2, ax2 = plt.subplots(figsize=(10, 8))
                ax2.pie(top_10, labels=top_10.index, autopct='%1.1f%%', startangle=140, wedgeprops={'width': 0.4})
                ax2.set_title(title2, fontproperties=font_prop, fontsize=16)
                st.pyplot(fig2)
                st.download_button("📥 下載比例圖", get_image_download(fig2), f"{current_city}_比例.png", "image/png")

            # --- 第二部分：互動式地圖 (效能優化版) ---
            st.divider()
            st.subheader(f"🗺️ {current_city} 行政區地理分佈")
            
            if os.path.exists(geojson_path):
                @st.cache_data
                def load_map_data(path, c_tai, c_ta):
                    gdf_raw = gpd.read_file(path)
                    res = gdf_raw[gdf_raw['COUNTYNAME'].isin([c_tai, c_ta])].copy()
                    res['TOWNNAME'] = res['TOWNNAME'].str.replace(f"{c_tai}|{c_ta}", "", regex=True).str.strip()
                    return res

                gdf = load_map_data(geojson_path, target_city_tai, target_city_ta)
                
                if not gdf.empty:
                    # 地圖初始化：改用輕量化底圖 CartoDB Positron
                    city_center = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
                    m = folium.Map(location=city_center, zoom_start=11, tiles="cartodbpositron")
                    
                    # 繪製色塊圖
                    folium.Choropleth(
                        geo_data=gdf,
                        data=all_counts.reset_index(),
                        columns=['index', 'Clean_Area'],
                        key_on='feature.properties.TOWNNAME',
                        fill_color='YlOrRd',
                        fill_opacity=0.6,
                        line_opacity=0.2,
                        legend_name='成交筆數'
                    ).add_to(m)

                    # 建立行政區標籤 (優化：固定像素大小，減少重繪)
                    stats = all_counts.to_dict()
                    for _, row in gdf.iterrows():
                        town = row['TOWNNAME']
                        if town in stats:
                            label_html = f"""<div style="font-family:'Microsoft JhengHei',sans-serif; text-align:center; color:black; text-shadow:1px 1px 2px white; pointer-events:none;">
                                             <div style="font-size:14px; font-weight:bold;">{town}</div>
                                             <div style="font-size:12px;">{stats[town]}筆</div></div>"""
                            folium.Marker(
                                [row.geometry.centroid.y, row.geometry.centroid.x],
                                icon=folium.DivIcon(icon_size=(80, 40), icon_anchor=(40, 20), html=label_html)
                            ).add_to(m)

                    # 🚀 效能核心：returned_objects=[] 阻止數據頻繁傳回後端
                    st_folium(m, width="100%", height=600, returned_objects=[])
                    st.info("💡 提示：地圖已優化加載速度。若需保存地圖，請使用截圖功能。")

        st.success("✅ 所有分析已就緒！")
        
    except Exception as e:
        st.error(f"處理檔案時發生錯誤：{e}")