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

# ttl=14400 означает, что сайт САМ каждые 4 часа будет проверять свежий файл на Google Диске!
@st.cache_resource(ttl=14400)
def load_data():
    with st.spinner("Загружаю актуальную базу данных..."):
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

    # Все поисковые колонки (включая ИНН и Предприятие) читаем строго как текст (str)!
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

def get_stem(word):
    word = word.lower().strip()
    if len(word) <= 4:
        return word
    return re.sub(
        r'(ами|ями|ого|его|ому|ему|ыми|ими|ая|яя|ое|ее|ые|ие|ой|ей|ый|ий|ом|ем|ам|ям|ах|ях|ов|ев|ью|ия|ии|а|я|о|е|ы|и|у|ю)$',
        '', word
    )

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
    reg_col = find_col(df, 'Реестров')
    old_reg_col = find_col(df, 'Первичн')
    exp_col = find_col(df, 'Срок действ')

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        prod_query = st.text_input("🏷️ Название товара:", placeholder="Например: пробирка")
    with col2:
        comp_query = st.text_input("🏭 Производитель:", placeholder="Например: Аспласт")
    with col3:
        inn_query = st.text_input("🔢 ИНН:", placeholder="Например: 7701314910")
    with col4:
        reg_query = st.text_input("📄 Реестровый номер:", placeholder="Например: 10084557")

    only_valid = st.checkbox("📅 Автоматически скрывать выписки с истекшим на сегодня сроком действия", value=True)

    if prod_query or comp_query or inn_query or reg_query:
        filtered_df = df

        if prod_query and prod_col:
            stems = [get_stem(w) for w in prod_query.split() if w.strip()]
            for stem in stems:
                filtered_df = filtered_df[filtered_df[prod_col].str.contains(re.escape(stem), case=False, na=False)]

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
        if total_found > 500:
            st.markdown(f"### Найдено записей: **{total_found}** *(показаны первые 500 — уточните запрос для сужения поиска)*")
            st.dataframe(filtered_df.head(500), width="stretch")
        else:
            st.markdown(f"### Найдено записей: **{total_found}**")
            st.dataframe(filtered_df, width="stretch")
    else:
        st.info("👆 Введите данные хотя бы в одно поле выше (можно комбинировать несколько полей сразу) и нажмите Enter.")

except Exception as e:
    st.error(f"Ошибка загрузки базы: {e}")
