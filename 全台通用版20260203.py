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
    # --- 修正：正確處理 CSV 與 Excel 讀取 ---
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, sheet_name=0, skiprows=[1])
        
        # 欄位偵測
        area_col = next((c for c in df.columns if any(k in str(c) for k in ['鄉鎮市區', '行政區'])), None)
        addr_col = next((c for c in df.columns if any(k in str(c) for k in ['土地位置', '建物門牌'])), None)
        price_col = next((c for c in df.columns if any(k in str(c) for k in ['總價元'])), None)

        if area_col:
            # 縣市偵測邏輯
            detect_text = "".join(df[addr_col].dropna().astype(str).head(50)) + \
                          "".join(df[area_col].dropna().astype(str).head(10)) + \
                          uploaded_file.name
                
            current_city = "臺南市"
            all_cities = ["臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "嘉義市", "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"]
            
            for city in all_cities:
                if city in detect_text or city.replace("臺", "台") in detect_text:
                    current_city = city
                    break
            
            target_city_ta = current_city.replace("臺", "台")
            target_city_tai = current_city.replace("台", "臺")
            
            df['Clean_Area'] = df[area_col].astype(str).str.replace(f"^{target_city_tai}|^{target_city_ta}", "", regex=True).str.strip()
            total_count = len(df)

            # --- 第一部分：成交量分析 ---
            st.subheader("📊 成交量分佈分析")
            c1, c2 = st.columns(2)
            all_counts = df['Clean_Area'].value_counts()
            top_10 = all_counts.head(10)
            
            with c1:
                title_bar1 = st.text_input("成交排行標題：", f"🏆 {current_city}成交量前十名行政區")
                fig1, ax1 = plt.subplots(figsize=(10, 7))
                sns.barplot(x=top_10.values, y=top_10.index, hue=top_10.index, palette='viridis', ax=ax1, legend=False)
                ax1.set_ylabel("") 
                max_v1 = top_10.max()
                for i, v in enumerate(top_10.values):
                    ax1.text(v + (max_v1 * 0.015), i, f'{int(v)}筆 ({ (v/total_count*100):.1f}%)', va='center', ha='left', fontproperties=font_prop)
                ax1.set_title(title_bar1, fontproperties=font_prop, fontsize=16)
                st.pyplot(fig1)
                st.download_button("📥 下載此圖", data=get_image_download(fig1, "bar1.png"), file_name=f"{current_city}_成交排行.png", mime="image/png")

            with c2:
                title_pie1 = st.text_input("成交比例標題：", f"📈 {current_city}成交比例 (Top 10+其他)")
                pie1_data = pd.concat([top_10, pd.Series({'其他': all_counts.iloc[10:].sum()})]) if len(all_counts) > 10 else all_counts
                fig_p1, ax_p1 = plt.subplots(figsize=(10, 8.5))
                ax_p1.pie(pie1_data, labels=pie1_data.index, autopct='%1.1f%%', colors=plt.get_cmap('tab20')(range(len(pie1_data))), wedgeprops={'width': 0.5}, startangle=140)
                ax_p1.text(0, 0, f'成交總筆數\n{total_count}筆', ha='center', va='center', fontproperties=font_prop, fontsize=15, fontweight='bold')
                ax_p1.set_title(title_pie1, fontproperties=font_prop, fontsize=16)
                st.pyplot(fig_p1)
                st.download_button("📥 下載此圖", data=get_image_download(fig_p1, "pie1.png"), file_name=f"{current_city}_成交比例.png", mime="image/png")

            # --- 第二部分：成交總價區間 ---
            st.divider()
            st.subheader("💰 成交總價區間分析")
            c3, c4 = st.columns(2)

            if price_col:
                p_data = pd.to_numeric(df[price_col], errors='coerce').dropna()
                bins = [0, 5e6, 1e7, 1.5e7, 2e7, float('inf')]
                labels = ['0-500萬', '500-1000萬', '1000-1500萬', '1500-2000萬', '2000萬以上']
                price_stats = pd.cut(p_data, bins=bins, labels=labels).value_counts().sort_index()

                with c3:
                    title_bar2 = st.text_input("價格區間標題：", f"🏘️ {current_city}成交總價區間")
                    fig2, ax2 = plt.subplots(figsize=(10, 7))
                    y_pos = range(len(labels))
                    ax2.barh(y_pos, price_stats.values, color=sns.color_palette('flare', len(labels)))
                    ax2.set_yticks(y_pos)
                    ax2.set_yticklabels(labels, fontproperties=font_prop)
                    ax2.invert_yaxis() 
                    max_v2 = price_stats.max()
                    for i, v in enumerate(price_stats.values):
                        pct = (v / len(p_data) * 100).round(1)
                        ax2.text(v + (max_v2 * 0.02), i, f'{int(v)}筆 ({pct}%)', va='center', ha='left', fontproperties=font_prop)
                    ax2.set_title(title_bar2, fontproperties=font_prop, fontsize=16)
                    st.pyplot(fig2)
                    st.download_button("📥 下載此圖", data=get_image_download(fig2, "bar2.png"), file_name=f"{current_city}_總價區間.png", mime="image/png")

                with c4:
                    title_pie2 = st.text_input("價格比例標題：", f"🪙 {current_city}成交總價比例")
                    fig_p2, ax_p2 = plt.subplots(figsize=(10, 8.5))
                    ax_p2.pie(price_stats, labels=price_stats.index, autopct='%1.1f%%', colors=sns.color_palette('husl', len(labels)), wedgeprops={'width': 0.5}, startangle=140)
                    ax_p2.text(0, 0, f'有效樣本\n{len(p_data)}筆', ha='center', va='center', fontproperties=font_prop, fontsize=15, fontweight='bold')
                    ax_p2.set_title(title_pie2, fontproperties=font_prop, fontsize=16)
                    st.pyplot(fig_p2)
                    st.download_button("📥 下載此圖", data=get_image_download(fig_p2, "pie2.png"), file_name=f"{current_city}_總價比例.png", mime="image/png")

            # --- 第三部分：互動式地圖 ---
            st.divider()
            st.subheader(f"🗺️ {current_city} 行政區成交地理分佈")
            
            if os.path.exists(geojson_path):
                @st.cache_data
                def get_map_data(path, city_tai, city_ta):
                    gdf_all = gpd.read_file(path)
                    gdf_inner = gdf_all[gdf_all['COUNTYNAME'].isin([city_tai, city_ta])].copy()
                    gdf_inner['TOWNNAME'] = gdf_inner['TOWNNAME'].astype(str).str.replace(f"{city_tai}|{city_ta}", "", regex=True).str.strip()
                    return gdf_inner

                gdf = get_map_data(geojson_path, target_city_tai, target_city_ta)
                
                if not gdf.empty:
                    map_stats = df['Clean_Area'].value_counts().reset_index()
                    map_stats.columns = ['區名', '筆數']
                    map_stats['比例'] = (map_stats['筆數'] / total_count * 100).round(1)
                    city_center = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
                    m = folium.Map(location=city_center, zoom_start=11, tiles=None, prefer_canvas=True)
                    
                    folium.TileLayer(tiles='https://wmts.nlsc.gov.tw/wmts/EMAP/default/GoogleMapsCompatible/{z}/{y}/{x}', attr='&copy; 國土測繪圖資服務雲', name='國土測繪電子地圖').add_to(m)
                    folium.Choropleth(geo_data=gdf, data=map_stats, columns=['區名', '筆數'], key_on='feature.properties.TOWNNAME', fill_color='YlOrRd', fill_opacity=0.4, line_opacity=0.2).add_to(m)

                    stats_dict = map_stats.set_index('區名').to_dict('index')
                    for _, row in gdf.iterrows():
                        town = row['TOWNNAME']
                        centroid = row.geometry.centroid
                        display_text = f"{int(stats_dict[town]['筆數'])}筆 ({stats_dict[town]['比例']}%)" if town in stats_dict else "0筆 (0.0%)"
                        label_html = f"""<div style="font-family: 'Noto Sans TC', 'Microsoft JhengHei', sans-serif; text-align: center; width: 120px; color: black; text-shadow: 1px 1px 2px white;">
                                         <div style="font-size: 1.1vw; font-weight: 900;">{town}</div>
                                         <div style="font-size: 0.9vw; font-weight: bold;">{display_text}</div></div>"""
                        folium.Marker(location=[centroid.y, centroid.x], icon=folium.DivIcon(icon_size=(120, 40), icon_anchor=(60, 20), html=label_html)).add_to(m)

                    st_folium(m, width="100%", height=650, key=f"map_{current_city}")

        st.success("✅ 數據分析完成！")
    except Exception as e:
        st.error(f"讀取檔案或分析時發生錯誤：{e}")