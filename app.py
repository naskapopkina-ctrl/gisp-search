import os
import re
import gc
import requests
import streamlit as st
import pandas as pd

# Настраиваем широкую страницу
st.set_page_config(layout="wide", page_title="Поиск ГИСП")

GDRIVE_FILE_ID = "1Z1Sq8z_kwfoB16aUNaQfxAiZDM0_ndnL"
LOCAL_FILE = "gisp_data.csv.gz"

def download_from_gdrive():
    url = f"https://drive.usercontent.google.com/download?id={GDRIVE_FILE_ID}&export=download&confirm=t"
    response = requests.get(url, stream=True, timeout=60)
    if response.status_code == 200:
        with open(LOCAL_FILE, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        return True
    return False

@st.cache_resource(ttl=14400)
def load_data():
    with st.spinner("⏳ Загружаю актуальную базу данных с Google Диска..."):
        download_from_gdrive()

    preview = pd.read_csv(LOCAL_FILE, sep=";", compression="gzip", nrows=5, dtype=str)
    export_info = str(preview.columns[0]) if "Время выгрузки" in str(preview.columns[0]) else "База актуальна"
    
    header_vals = list(preview.columns)
    skip_lines = 1
    
    if 'ИНН' not in header_vals:
        for i in range(len(preview)):
            if 'ИНН' in preview.iloc[i].values:
                header_vals = list(preview.iloc[i].values)
                skip_lines = i + 2
                break

    new_cols = []
    for idx, col in enumerate(header_vals):
        if pd.isna(col) or not str(col).strip():
            new_cols.append(f"Колонка_{idx}")
        elif str(col).strip() in new_cols:
            new_cols.append(f"{str(col).strip()}_{idx}")
        else:
            new_cols.append(str(col).strip())

    dtype_dict = {}
    for col in new_cols:
        if col.startswith(('Наимено', 'Предприя', 'ИНН', 'ОГРН', 'Реестров', 'Первичн', 'Срок действ')):
            dtype_dict[col] = str
        else:
            dtype_dict[col] = "category"

    df = pd.read_csv(
        LOCAL_FILE,
        sep=";",
        compression="gzip",
        skiprows=skip_lines,
        names=new_cols,
        dtype=dtype_dict,
        low_memory=False
    )
    gc.collect()
    return df, export_info

# Улучшенный умный поиск: отрезает окончания (включая "ь" и "й" для "простынь") и учитывает е/ё
def get_stem_pattern(word):
    word = word.lower().strip()
    if len(word) > 4:
        word = re.sub(
            r'(ами|ями|ого|его|ому|ему|ыми|ими|ая|яя|ое|ее|ые|ие|ой|ей|ый|ий|ую|юю|ых|их|ом|ем|ам|ям|ах|ях|ов|ев|ью|ья|ье|ьи|ия|ии|а|я|о|е|ы|и|у|ю|ь|й)$',
            '', word
        )
    escaped = re.escape(word)
    # Делаем так, чтобы "е" и "ё" находили друг друга
    return re.sub(r'[её]', '[её]', escaped)

def find_col(df, prefix):
    cols = [col for col in df.columns if str(col).startswith(prefix)]
    return cols[0] if cols else None

top_col1, top_col2 = st.columns([4, 1])
with top_col1:
    st.title("Умный поиск по реестру ГИСП 🔍")
with top_col2:
    st.write("")
    if st.button("🔄 Обновить базу с Google Диска"):
        st.cache_resource.clear()
        st.rerun()

try:
    df, export_info = load_data()
    st.success(f"✅ База готова к работе! Всего записей: **{len(df)}** | 🕒 **{export_info}**")
    
    prod_col = find_col(df, 'Наимено')
    comp_col = find_col(df, 'Предприя')
    inn_col = find_col(df, 'ИНН')
    ogrn_col = find_col(df, 'ОГРН')
    reg_col = find_col(df, 'Реестров')
    old_reg_col = find_col(df, 'Первичн')
    exp_col = find_col(df, 'Срок действ')
    okpd_col = find_col(df, 'ОКПД')
    tnved_col = find_col(df, 'ТН ВЭД')

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        prod_query = st.text_input("🏷️ Название товара:", placeholder="Например: простынь одноразовая")
    with col2:
        comp_query = st.text_input("🏭 Производитель:", placeholder="Например: Аспласт")
    with col3:
        inn_query = st.text_input("🔢 ИНН:", placeholder="Например: 7701314910")
    with col4:
        reg_query = st.text_input("📄 Реестровый номер:", placeholder="Например: 10084557")

    only_valid = st.checkbox("📅 Автоматически скрывать выписки с истекшим на сегодня сроком действия", value=True)

    if prod_query or comp_query or inn_query or reg_query:
        # Показываем наглядный индикатор процесса поиска
        with st.spinner("🔎 Идет поиск по реестру ГИСП, подождите пару секунд..."):
            filtered_df = df

            if prod_query and prod_col:
                patterns = [get_stem_pattern(w) for w in prod_query.split() if w.strip()]
                for pat in patterns:
                    filtered_df = filtered_df[filtered_df[prod_col].str.contains(pat, case=False, na=False)]

            if comp_query and comp_col:
                words = [w.strip() for w in comp_query.split() if w.strip()]
                for w in words:
                    filtered_df = filtered_df[filtered_df[comp_col].str.contains(re.escape(w), case=False, na=False)]

            if inn_query and inn_col:
                filtered_df = filtered_df[filtered_df[inn_col].str.contains(re.escape(inn_query.strip()), case=False, na=False)]

            if reg_query and reg_col:
                q = re.escape(reg_query.strip())
                if old_reg_col:
                    mask = (
                        filtered_df[reg_col].str.contains(q, case=False, na=False) | 
                        filtered_df[old_reg_col].str.contains(q, case=False, na=False)
                    )
                    filtered_df = filtered_df[mask]
                else:
                    filtered_df = filtered_df[filtered_df[reg_col].str.contains(q, case=False, na=False)]

            if only_valid and exp_col and len(filtered_df) > 0:
                exp_dates = pd.to_datetime(filtered_df[exp_col], errors='coerce')
                today = pd.Timestamp.now().normalize()
                filtered_df = filtered_df[exp_dates.isna() | (exp_dates >= today)]

            total_found = len(filtered_df)
            display_df = filtered_df.head(500) if total_found > 500 else filtered_df

            # Настраиваем ширину колонок: Наименование — широкое, а пустые/FALSE — узкие
            col_config = {}
            for col in display_df.columns:
                if col == prod_col:
                    col_config[col] = st.column_config.TextColumn(col, width="large")
                elif col == comp_col:
                    col_config[col] = st.column_config.TextColumn(col, width="medium")
                else:
                    # Проверяем, состоит ли колонка в основном из пустых значений или FALSE/Нет
                    sample = display_df[col].astype(str)
                    empty_or_false = sample.isin(['nan', 'None', '', 'FALSE', 'False', 'Нет']).mean()
                    if empty_or_false > 0.7:
                        col_config[col] = st.column_config.Column(col, width="small")

            # Ставим самые важные колонки (включая Наименование!) на первый экран слева
            priority_cols = [c for c in [prod_col, reg_col, comp_col, inn_col, exp_col, okpd_col, tnved_col, ogrn_col] if c]
            other_cols = [c for c in display_df.columns if c not in priority_cols]
            ordered_cols = priority_cols + other_cols

        if total_found > 500:
            st.markdown(f"### Найдено записей: **{total_found}** *(показаны первые 500 — уточните запрос для сужения поиска)*")
        else:
            st.markdown(f"### Найдено записей: **{total_found}**")
            
        st.dataframe(display_df, width="stretch", column_config=col_config, column_order=ordered_cols)
    else:
        st.info("👆 Введите данные хотя бы в одно поле выше (можно комбинировать несколько полей сразу) и нажмите Enter.")

except Exception as e:
    st.error(f"Ошибка загрузки базы: {e}")
