import os
import re
import gc
import requests
import streamlit as st
import pandas as pd

# Настраиваем широкую страницу
st.set_page_config(layout="wide", page_title="Поиск ГИСП")

# ==============================================================================
# 📖 СЛОВАРЬ НАРОДНЫХ НАЗВАНИЙ И СОКРАЩЕНИЙ ПРОИЗВОДИТЕЛЕЙ
# Чтобы добавить новое сокращение, просто допиши строчку ниже по образцу:
# "короткое_название": "официальное название в реестре",
# (Если вариантов несколько, раздели их вертикальной чертой | )
# ==============================================================================
COMPANY_ALIASES = {
    "змт": "завод медицинских технологий|здравмедтех",
    "здравмедтех": "завод медицинских технологий|здравмедтех",
    "зравмедтех": "завод медицинских технологий|здравмедтех",
    "епз": "елатомский приборный завод",
    "еламед": "елатомский приборный завод",
    "елатомовский": "елатомский",
}

# Автоматическое сокращение организационно-правовых форм в таблице
LEGAL_FORMS = {
    "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ": "ООО",
    "ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО": "ПАО",
    "ЗАКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО": "ЗАО",
    "НЕПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО": "НАО",
    "ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО": "ОАО",
    "АКЦИОНЕРНОЕ ОБЩЕСТВО": "АО",
    "ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ": "ИП",
    "ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ УНИТАРНОЕ ПРЕДПРИЯТИЕ": "ФГУП",
    "ФЕДЕРАЛЬНОЕ КАЗЕННОЕ ПРЕДПРИЯТИЕ": "ФКП",
    "НАУЧНО-ПРОИЗВОДСТВЕННОЕ ОБЪЕДИНЕНИЕ": "НПО",
    "НАУЧНО-ПРОИЗВОДСТВЕННОЕ ПРЕДПРИЯТИЕ": "НПП",
}

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

def shorten_company_name(name):
    if not isinstance(name, str):
        return name
    res = name
    for full_form, short_form in LEGAL_FORMS.items():
        res = re.sub(re.escape(full_form), short_form, res, flags=re.IGNORECASE)
    return res

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

    comp_cols = [c for c in df.columns if str(c).startswith('Предприя')]
    if comp_cols:
        c_col = comp_cols[0]
        unique_names = df[c_col].dropna().unique()
        name_map = {name: shorten_company_name(name) for name in unique_names}
        df[c_col] = df[c_col].map(name_map)

    gc.collect()
    return df, export_info

# Умный поиск: отрезает окончания (включая "ь" и "й") и учитывает е/ё
def get_stem_pattern(word):
    word = word.lower().strip()
    if len(word) > 4:
        word = re.sub(
            r'(ами|ями|ого|его|ому|ему|ыми|ими|ая|яя|ое|ее|ые|ие|ой|ей|ый|ий|ую|юю|ых|их|ом|ем|ам|ям|ах|ях|ов|ев|ью|ья|ье|ьи|ия|ии|а|я|о|е|ы|и|у|ю|ь|й)$',
            '', word
        )
    escaped = re.escape(word)
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

# ==============================================================================
# 💬 БЛОК ПОДСКАЗОК И СВОРАЧИВАЕМЫХ СТРОК (ЗДЕСЬ МОЖНО МЕНЯТЬ ТЕКСТ)
# ==============================================================================
with st.expander("❓ Что делать, если выводит ошибку, и как перейти в карточку товара ГИСП?"):
    st.markdown(
        """
        * **Как быстро открыть карточку товара в Каталоге ГИСП:** нажмите кнопку **«В Каталог ↗»** рядом с реестровым номером — откроется быстрый Каталог ГИСП, уже отфильтрованный по этому производителю! (Если у завода много товаров, просто вставьте скопированный **Реестровый номер** в поле *«Реестровая запись»* справа в Каталоге).
        * **Если таблица не загрузилась:** попробуйте нажать кнопку **«🔄 Обновить базу с Google Диска»** в правом верхнем углу страницы.
        * **По всем вопросам и предложениям** (или чтобы добавить новое сокращение производителя) пишите на почту: **[svch1073@yandex.ru](mailto:svch1073@yandex.ru)**
        """
    )

try:
    df, export_info = load_data()
    st.success(
        f"✅ База готова к работе! Всего записей: **{len(df)}** | "
        f"🕒 **{export_info}** | "
        f"📅 *Обновление происходит в 10:00 каждого буднего дня*"
    )
    
    prod_col = find_col(df, 'Наимено')
    comp_col = find_col(df, 'Предприя')
    inn_col = find_col(df, 'ИНН')
    ogrn_col = find_col(df, 'ОГРН')
    reg_col = find_col(df, 'Реестров')
    old_reg_col = find_col(df, 'Первичн')
    exp_col = find_col(df, 'Срок действ')
    okpd_col = find_col(df, 'ОКПД')
    tnved_col = find_col(df, 'ТН ВЭД')

    with st.form("search_form"):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            prod_query = st.text_input("🏷️ Название товара:", placeholder="Например: простынь одноразовая")
        with col2:
            comp_query = st.text_input("🏭 Производитель:", placeholder="Например: ЕПЗ или ЗМТ")
        with col3:
            inn_query = st.text_input("🔢 ИНН:", placeholder="Например: 7701314910")
        with col4:
            reg_query = st.text_input("📄 Реестровый номер:", placeholder="Например: 10084557")

        submitted = st.form_submit_button("🔍 Найти", type="primary")

    if prod_query or comp_query or inn_query or reg_query:
        status_box = st.empty()
        status_box.warning("⏳ Идет поиск по реестру ГИСП и загрузка таблицы, пожалуйста подождите...")

        filtered_df = df

        if prod_query and prod_col:
            patterns = [get_stem_pattern(w) for w in prod_query.split() if w.strip()]
            for pat in patterns:
                filtered_df = filtered_df[filtered_df[prod_col].str.contains(pat, case=False, na=False)]

        if comp_query and comp_col:
            q_clean = comp_query.lower().strip()
            if q_clean in COMPANY_ALIASES:
                filtered_df = filtered_df[filtered_df[comp_col].str.contains(COMPANY_ALIASES[q_clean], case=False, na=False)]
            else:
                words = [w.strip().strip('"\'«»') for w in comp_query.split() if w.strip()]
                for w in words:
                    w_low = w.lower()
                    if w_low in COMPANY_ALIASES:
                        pat = COMPANY_ALIASES[w_low]
                    else:
                        pat = get_stem_pattern(w)
                    filtered_df = filtered_df[filtered_df[comp_col].str.contains(pat, case=False, na=False)]

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

        total_found = len(filtered_df)
        display_df = (filtered_df.head(500) if total_found > 500 else filtered_df).copy()

        for c in display_df.select_dtypes(include=['category']).columns:
            display_df[c] = display_df[c].astype(object)
            
        if exp_col and exp_col in display_df.columns:
            display_df[exp_col] = display_df[exp_col].str.replace(" 00:00:00", "", regex=False)

        # Создаем кликабельную колонку со ссылкой сразу в быстрый Каталог ГИСП по ОГРН завода
        link_col = "🔗 Каталог ГИСП"
        if ogrn_col and ogrn_col in display_df.columns:
            display_df[link_col] = "https://gisp.gov.ru/goods/#/?company_ogrn=" + display_df[ogrn_col].astype(str).str.strip()

        col_config = {}
        for col in display_df.columns:
            if col == prod_col:
                col_config[col] = st.column_config.TextColumn(col, width=700)
            elif col == link_col:
                col_config[col] = st.column_config.LinkColumn(col, display_text="В Каталог ↗", width=125)
            elif col == comp_col:
                col_config[col] = st.column_config.TextColumn(col, width=230)
            elif col in [reg_col, inn_col, exp_col, okpd_col, tnved_col, ogrn_col]:
                col_config[col] = st.column_config.TextColumn(col, width=110)
            else:
                is_empty_or_false = (
                    display_df[col].isna() | 
                    display_df[col].astype(str).str.strip().isin(['nan', 'None', '', 'FALSE', 'False', 'Нет'])
                )
                if is_empty_or_false.mean() > 0.7:
                    col_config[col] = st.column_config.Column(col, width="small")

        priority_cols = [c for c in [prod_col, reg_col, link_col, comp_col, inn_col, exp_col, okpd_col, tnved_col, ogrn_col] if c and c in display_df.columns]
        other_cols = [c for c in display_df.columns if c not in priority_cols]
        ordered_cols = priority_cols + other_cols
        display_df = display_df[ordered_cols]

        def highlight_expiring(df_to_style):
            styles = pd.DataFrame("", index=df_to_style.index, columns=df_to_style.columns)
            if exp_col and exp_col in df_to_style.columns:
                today = pd.Timestamp.now().normalize()
                exp_dates = pd.to_datetime(df_to_style[exp_col], errors='coerce')
                days_left = (exp_dates - today).dt.days
                
                yellow_mask = (days_left > 183) & (days_left <= 365)
                red_mask = days_left <= 183
                
                styles.loc[yellow_mask, :] = "background-color: #fff6d1; color: #1a1a1a;"
                styles.loc[red_mask, :] = "background-color: #ffe6e6; color: #1a1a1a;"
            return styles

        styled_df = display_df.style.apply(highlight_expiring, axis=None)

        if total_found > 500:
            st.markdown(f"### Найдено записей: **{total_found}** *(показаны первые 500 — уточните запрос для сужения поиска)*")
        else:
            st.markdown(f"### Найдено записей: **{total_found}**")
            
        st.caption("🎨 **Подсветка сроков действия:** 🔴 *Бледно-красный* — осталось полгода и меньше | 🟡 *Бледно-желтый* — остался год и меньше")
        st.dataframe(styled_df, width="stretch", column_config=col_config)
        
        status_box.empty()
    else:
        st.info("👆 Введите данные хотя бы в одно поле выше и нажмите кнопку «🔍 Найти» (или клавишу Enter).")

except Exception as e:
    st.error(f"Ошибка загрузки базы: {e}. Пожалуйста, напишите на почту svch1073@yandex.ru")
