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
    st.sidebar.error("❌ 找不到字體檔")
    font_prop = None

plt.rcParams['axes.unicode_minus'] = False

def get_image_download(fig, filename):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', dpi=300)
    buf.seek(0)
    return buf

# --- 3. 核心邏輯 ---
st.title("🏙️ 全台實價登錄分析系統")

uploaded_file = st.sidebar.file_uploader("請上傳內政部資料", type=['xls', 'xlsx', 'csv'])

if uploaded_file:
    try:
        # 正確讀取檔案
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, sheet_name=0, skiprows=[1])
        
        # 欄位偵測
        area_col = next((c for c in df.columns if any(k in str(c) for k in ['鄉鎮市區', '行政區'])), None)
        addr_col = next((c for c in df.columns if any(k in str(c) for k in ['土地位置', '建物門牌'])), None)
        price_col = next((c for c in df.columns if any(k in str(c) for k in ['總價元'])), None)

        if area_col:
            # 縣市偵測
            detect_text = "".join(df[addr_col].dropna().astype(str).head(30)) + uploaded_file.name
            current_city = "臺南市"
            all_cities = ["臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "嘉義市", "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"]
            for city in all_cities:
                if city in detect_text or city.replace("臺", "台") in detect_text:
                    current_city = city
                    break
            
            target_city_tai = current_city.replace("台", "臺")
            target_city_ta = current_city.replace("臺", "台")
            df['Clean_Area'] = df[area_col].astype(str).str.replace(f"^{target_city_tai}|^{target_city_ta}", "", regex=True).str.strip()
            total_count = len(df)
            all_counts = df['Clean_Area'].value_counts()

            # --- 第一部分：成交分析 ---
            st.subheader("📊 成交數據概覽")
            c1, c2 = st.columns(2)
            with c1:
                top_10 = all_counts.head(10)
                fig1, ax1 = plt.subplots(figsize=(10, 7))
                sns.barplot(x=top_10.values, y=top_10.index, hue=top_10.index, palette='viridis', ax=ax1, legend=False)
                ax1.set_title(f"🏆 {current_city}成交排行", fontproperties=font_prop, fontsize=16)
                st.pyplot(fig1)
            with c2:
                # 簡單顯示總價分佈
                if price_col:
                    p_series = pd.to_numeric(df[price_col], errors='coerce').dropna()
                    fig2, ax2 = plt.subplots(figsize=(10, 7))
                    sns.histplot(p_series, bins=20, kde=True, ax=ax2, color='orange')
                    ax2.set_title("💰 總價分佈統計", fontproperties=font_prop)
                    st.pyplot(fig2)

            # --- 第二部分：地理分佈 (國土測繪雲 + 動態縮放標籤) ---
            st.divider()
            st.subheader(f"🗺️ {current_city} 行政區地理分佈 (國土測繪雲版)")
            
            if os.path.exists(geojson_path):
                @st.cache_data
                def get_map_data(path, c_tai, c_ta):
                    gdf_all = gpd.read_file(path)
                    res = gdf_all[gdf_all['COUNTYNAME'].isin([c_tai, c_ta])].copy()
                    res['TOWNNAME'] = res['TOWNNAME'].str.replace(f"{c_tai}|{c_ta}", "", regex=True).str.strip()
                    return res

                gdf = get_map_data(geojson_path, target_city_tai, target_city_ta)
                
                if not gdf.empty:
                    # 計算中心點
                    map_center = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
                    
                    # 🚀 堅持使用 Prefer_canvas 以提升大量標籤的渲染速度
                    m = folium.Map(location=map_center, zoom_start=11, tiles=None, prefer_canvas=True)
                    
                    # 🚀 1. 國土測繪雲圖層 (EMAP)
                    folium.TileLayer(
                        tiles='https://wmts.nlsc.gov.tw/wmts/EMAP/default/GoogleMapsCompatible/{z}/{y}/{x}',
                        attr='&copy; 國土測繪圖資服務雲',
                        name='國土測繪電子地圖',
                        overlay=False,
                        control=True
                    ).add_to(m)

                    # 2. 著色層 (Choropleth)
                    folium.Choropleth(
                        geo_data=gdf, data=all_counts.reset_index(), columns=['index', 'Clean_Area'],
                        key_on='feature.properties.TOWNNAME', fill_color='YlOrRd',
                        fill_opacity=0.4, line_opacity=0.2
                    ).add_to(m)

                    # 3. 標籤層 (維持動態縮放 vw)
                    stats = all_counts.to_dict()
                    for _, row in gdf.iterrows():
                        town = row['TOWNNAME']
                        if town in stats:
                            display_text = f"{int(stats[town])}筆"
                            # 🚀 維持您的動態縮放 vw 設定
                            label_html = f"""<div style="font-family: 'Noto Sans TC', sans-serif; text-align: center; width: 120px; color: black; text-shadow: 1px 1px 2px white; pointer-events: none;">
                                             <div style="font-size: 1.1vw; font-weight: 900;">{town}</div>
                                             <div style="font-size: 0.9vw; font-weight: bold;">{display_text}</div></div>"""
                            folium.Marker(
                                location=[row.geometry.centroid.y, row.geometry.centroid.x],
                                icon=folium.DivIcon(icon_size=(120, 40), icon_anchor=(60, 20), html=label_html)
                            ).add_to(m)

                    # 🚀 關鍵：加入 returned_objects=[] 徹底解決變白卡頓問題
                    st_folium(m, width="100%", height=700, key=f"map_{current_city}", returned_objects=[])

        st.success("✅ 數據分析完成！")
    except Exception as e:
        st.error(f"分析時發生錯誤：{e}")