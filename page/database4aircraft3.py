import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO
import os
import re
import zipfile  # <--- 新增
import numpy as np  # <--- 新增
import io  # 新增 io 用于 zip 处理
import time  # 1. 引入time模块，用于UI延时

# ================= 配置部分 =================
# 设置 Matplotlib 中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# ================= 数据库逻辑 =================

def create_connection(db_file):
    """创建数据库连接"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        st.error(f"数据库连接错误: {e}")
    return conn


def init_db(conn):
    """初始化数据库表 (包含字段迁移逻辑)"""
    try:
        cursor = conn.cursor()

        # 1. 创建感应电流表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS induced_current (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aircraft_model TEXT NOT NULL,
            current_probe_position TEXT NOT NULL,
            antenna_position TEXT NOT NULL,
            antenna_type TEXT NOT NULL,
            antenna_polarization TEXT NOT NULL,
            antenna_incident_angle TEXT NOT NULL,
            data_content TEXT NOT NULL,
            frequency_unit TEXT NOT NULL,
            notes TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 2. 创建感应电场表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS induced_field (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aircraft_model TEXT NOT NULL,
            receiving_antenna_position TEXT NOT NULL,
            antenna_position TEXT NOT NULL,
            antenna_type TEXT NOT NULL,
            antenna_polarization TEXT NOT NULL,
            antenna_incident_angle TEXT NOT NULL,
            data_content TEXT NOT NULL,
            frequency_unit TEXT NOT NULL,
            notes TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # --- 数据库迁移逻辑: 检查并添加 data_stat_type 字段 ---
        try:
            cursor.execute("SELECT data_stat_type FROM induced_field LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE induced_field ADD COLUMN data_stat_type TEXT DEFAULT 'MAX'")
            st.toast("数据库结构已更新：添加了 data_stat_type 字段", icon="✅")
        # --------------------------------------------------

        conn.commit()
    except sqlite3.Error as e:
        st.error(f"数据库初始化错误: {e}")


# ================= 辅助功能函数 =================

def init_session_state():
    if 'selected_id' not in st.session_state:
        st.session_state.selected_id = None
    if 'records' not in st.session_state:
        st.session_state.records = []
    # 批量导入缓存
    if 'batch_hirf_cache' not in st.session_state:
        st.session_state.batch_hirf_cache = None


def parse_data_file(uploaded_file):
    """解析上传的文件内容"""
    try:
        content = uploaded_file.getvalue().decode("utf-8", errors='ignore')
        return content
    except Exception as e:
        st.error(f"解析数据文件错误: {e}")
        return None


def convert_to_mhz(freq, unit):
    """将频率转换为MHz单位"""
    if unit == "Hz":
        return freq / 1e6
    elif unit == "KHz":
        return freq / 1e3
    elif unit == "MHz":
        return freq
    elif unit == "GHz":
        return freq * 1e3
    else:
        return freq


def validate_frequency_range(data_content, frequency_unit, table_name):
    """验证频率范围是否符合要求"""
    try:
        df = pd.read_csv(StringIO(data_content), sep='\t' if '\t' in data_content else ',', header=None)
        if df.shape[1] < 1:
            return False, "数据文件需要至少包含频率列"

        frequencies = df.iloc[:, 0]
        frequencies = pd.to_numeric(frequencies, errors='coerce').dropna()

        if frequencies.empty:
            return False, "未找到有效的频率数值"

        frequencies_mhz = frequencies.apply(lambda x: convert_to_mhz(x, frequency_unit))

        if table_name == "induced_current":
            min_freq, max_freq = 0.5, 400
            data_type = "感应电流"
        else:  # induced_field
            min_freq, max_freq = 100, 8000
            data_type = "感应电磁"

        f_min = frequencies_mhz.min()
        f_max = frequencies_mhz.max()

        if f_min < min_freq * 0.9:
            return False, f"{data_type}频率过低: {f_min:.2f}MHz (标准>{min_freq}MHz)"
        if f_max > max_freq * 1.1:
            return False, f"{data_type}频率过高: {f_max:.2f}MHz (标准<{max_freq}MHz)"

        return True, "频率范围验证通过"
    except Exception as e:
        return False, f"频率验证错误: {e}"


def plot_data(data_content, title, ylabel):
    """绘制数据曲线"""
    if not data_content:
        st.warning("没有可用的数据")
        return

    try:
        data = pd.read_csv(StringIO(data_content), sep='\t' if '\t' in data_content else ',', header=None)
        if len(data) == 0:
            st.warning("数据为空")
            return

        fig, ax = plt.subplots(figsize=(10, 4))
        x_data = pd.to_numeric(data.iloc[:, 0], errors='coerce')
        y_data = pd.to_numeric(data.iloc[:, 1], errors='coerce')
        mask = x_data.notna() & y_data.notna()

        ax.plot(x_data[mask], y_data[mask])
        ax.set_xlabel('Frequency')
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, linestyle='--', alpha=0.6)
        st.pyplot(fig)
    except Exception as e:
        st.error(f"绘图错误: {e}")


def smart_parse_hirf_filename(filename):
    """智能解析 HIRF 文件名"""
    info = {
        "aircraft_model": "",
        "position": "",
        "antenna_pos": "",
        "polarization": "垂直极化",
        "angle": "0",
        "type": "MAX"
    }

    name_no_ext = filename.rsplit('.', 1)[0]
    parts = name_no_ext.split('_')

    if len(parts) >= 1: info["aircraft_model"] = parts[0]
    if len(parts) >= 2: info["position"] = parts[1]
    if len(parts) >= 3: info["antenna_pos"] = parts[2]

    if "Hor" in name_no_ext or "水平" in name_no_ext:
        info["polarization"] = "水平极化"
    elif "Ver" in name_no_ext or "垂直" in name_no_ext:
        info["polarization"] = "垂直极化"

    if "MIN" in name_no_ext.upper():
        info["type"] = "MIN"
    elif "AV" in name_no_ext.upper():
        info["type"] = "AV"
    else:
        info["type"] = "MAX"

    return info


# ================= 核心操作函数 =================

def add_record_db(conn, table_name, record_dict):
    """通用添加记录函数"""
    try:
        cursor = conn.cursor()
        if table_name == "induced_current":
            cursor.execute(f'''
            INSERT INTO {table_name} 
            (aircraft_model, current_probe_position, antenna_position, antenna_type, 
             antenna_polarization, antenna_incident_angle, data_content, frequency_unit, notes)
            VALUES (:aircraft_model, :current_probe_position, :antenna_position, :antenna_type, 
             :antenna_polarization, :antenna_incident_angle, :data_content, :frequency_unit, :notes)
            ''', record_dict)
        else:
            cursor.execute(f'''
            INSERT INTO {table_name} 
            (aircraft_model, receiving_antenna_position, antenna_position, antenna_type, 
             antenna_polarization, antenna_incident_angle, data_content, frequency_unit, notes, data_stat_type)
            VALUES (:aircraft_model, :receiving_antenna_position, :antenna_position, :antenna_type, 
             :antenna_polarization, :antenna_incident_angle, :data_content, :frequency_unit, :notes, :data_stat_type)
            ''', record_dict)
        conn.commit()
        return True
    except sqlite3.Error as e:
        st.error(f"添加记录数据库错误: {e}")
        return False


def delete_record(conn, table_name, record_id):
    """删除记录，返回成功状态而不是直接打印"""
    try:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM {table_name} WHERE id=?', (record_id,))
        conn.commit()
        return True  # 返回True表示成功
    except sqlite3.Error as e:
        st.error(f"删除记录错误: {e}")
        return False


def query_records(conn, table_name, conditions=None):
    try:
        cursor = conn.cursor()
        if conditions:
            query = f'SELECT * FROM {table_name} WHERE '
            query += ' AND '.join([f"{k}=?" for k in conditions.keys()])
            cursor.execute(query, tuple(conditions.values()))
        else:
            cursor.execute(f'SELECT * FROM {table_name} ORDER BY id DESC')

        columns = [column[0] for column in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return records
    except sqlite3.Error as e:
        st.error(f"查询记录错误: {e}")
        return []


def generate_download_file(record, table_name):
    """生成下载文件"""
    try:
        if table_name == "induced_current":
            filename_fields = [
                record.get('aircraft_model'),
                record.get('current_probe_position'),
                record.get('antenna_position'),
                record.get('antenna_type'),
                record.get('antenna_polarization'),
                record.get('antenna_incident_angle'),
                record.get('frequency_unit')
            ]
        else:
            filename_fields = [
                record.get('aircraft_model'),
                record.get('receiving_antenna_position'),
                record.get('data_stat_type', 'MAX'),
                record.get('antenna_position'),
                record.get('antenna_type'),
                record.get('antenna_polarization'),
                record.get('antenna_incident_angle'),
                record.get('frequency_unit')
            ]

        valid_parts = []
        for field in filename_fields:
            if field:
                s_val = str(field).strip()
                s_val = s_val.replace('/', '-').replace('\\', '-')
                valid_parts.append(s_val)

        if valid_parts:
            filename = "_".join(valid_parts) + ".txt"
        else:
            filename = "unknown_data.txt"

        data_content = record['data_content']
        return filename, data_content

    except Exception as e:
        st.error(f"生成下载文件错误: {e}")
        return "error_data.txt", ""


# ================= 主程序 =================

def main():
    #########0  显示公司logo
    LOGO_PATH = "company_logo.jpg"
    if not os.path.exists(LOGO_PATH):
        # 模拟 wyz_io 避免报错
        class MockIo:
            @staticmethod
            def image_to_base64(p): return ""

        wyz_io = MockIo()
        logo_html = ""
    else:
        try:
            import wyz_io
            logo_base64 = wyz_io.image_to_base64(LOGO_PATH)
            logo_html = f"""
            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                <img src="data:image/jpeg;base64,{logo_base64}" alt="公司标徽" style="height: 60px;">
                <h3 style="margin: 0; font-size: 42px;">中航通飞华南飞机工业有限公司</h3>
            </div>
            """
        except ImportError:
            logo_html = ""

    if logo_html:
        st.markdown(logo_html, unsafe_allow_html=True)

    init_session_state()
    st.title("飞机HIRF环境数据库系统")

    db_file = "aircraft_hirf.db"
    conn = create_connection(db_file)
    if conn is not None:
        init_db(conn)
    else:
        st.error("无法连接到数据库!")
        return

    # 侧边栏
    st.sidebar.title("导航")
    menu = ["感应电流数据库 (0.5MHz~400MHz)", "感应电场数据库 (100MHz~8GHz)", "关于"]
    database_type = st.sidebar.selectbox("数据库选择", menu)

    if 'prev_database_type' not in st.session_state:
        st.session_state.prev_database_type = database_type
    elif st.session_state.prev_database_type != database_type:
        st.session_state.records = []
        st.session_state.selected_id = None
        st.session_state.batch_hirf_cache = None
        st.session_state.prev_database_type = database_type

    if "感应电流" in database_type:
        table_name = "induced_current"
        ylabel = "Current (A)"
        probe_label = "电流探针位置"
        is_field_db = False
    elif "感应电场" in database_type:
        table_name = "induced_field"
        ylabel = "Field Strength (V/m)"
        probe_label = "接收天线位置"
        is_field_db = True
    else:
        st.markdown("### 关于系统\n本系统用于管理飞机HIRF测试数据。")
        conn.close()
        return

    operation = st.sidebar.radio("选择操作", ("查询数据", "添加数据", "修改数据", "删除数据"))

    # ================= 1. 查询数据 =================
    # ================= 1. 查询数据 =================
    if operation == "查询数据":
        st.header(f"{database_type} - 查询")

        # --- A. 查询条件输入区域 ---
        col1, col2, col3 = st.columns(3)
        with col1:
            aircraft_model = st.text_input("飞机型号", "")
        with col2:
            probe_field = st.text_input(probe_label, "")
        with col3:
            if is_field_db:
                data_stat = st.selectbox("数据类型", ["全部", "MAX", "MIN", "AV"])
            else:
                data_stat = None

        # --- B. 执行查询 ---
        if st.button("查询"):
            cond = {}
            if aircraft_model: cond["aircraft_model"] = aircraft_model
            if probe_field:
                key = "current_probe_position" if not is_field_db else "receiving_antenna_position"
                cond[key] = probe_field
            if is_field_db and data_stat and data_stat != "全部":
                cond["data_stat_type"] = data_stat

            records = query_records(conn, table_name, cond)
            st.session_state.records = records
            st.session_state.selected_id = None

        # --- C. 结果显示与批量操作 ---
        if st.session_state.records:
            df_origin = pd.DataFrame(st.session_state.records)

            # 1. 准备显示数据：添加"选择"列，移除大文本列以免卡顿
            df_display = df_origin.copy()
            if 'data_content' in df_display.columns:
                df_display = df_display.drop(columns=['data_content'])
            df_display.insert(0, "选择", False)

            st.markdown("### 📊 数据列表 (请勾选需要下载的数据)")

            # 2. 使用 data_editor 进行交互
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "选择": st.column_config.CheckboxColumn("选择", help="勾选以加入批量下载", default=False),
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "aircraft_model": st.column_config.TextColumn("飞机型号", disabled=True),
                    # 其他列保持默认
                },
                disabled=["id", "aircraft_model", "current_probe_position", "receiving_antenna_position"],
                hide_index=True,
                use_container_width=True
            )

            # 3. 获取选中行
            selected_rows = edited_df[edited_df["选择"] == True]

            # 4. 批量下载逻辑
            with st.expander("📦 批量下载操作区", expanded=True):
                col_btn, col_info = st.columns([1, 2])
                with col_info:
                    st.info(f"当前筛选结果共 {len(df_origin)} 条，您已勾选 **{len(selected_rows)}** 条。")

                with col_btn:
                    if st.button("生成选中数据的压缩包 (ZIP)"):
                        if selected_rows.empty:
                            st.error("请先在上方表格中至少勾选一条数据！")
                        else:
                            zip_buffer = io.BytesIO()
                            file_count = 0

                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                for index, row in selected_rows.iterrows():
                                    # 回溯原始记录以获取 data_content
                                    original_record = df_origin[df_origin['id'] == row['id']].iloc[0]

                                    # 复用你原有的 generate_download_file 函数生成标准文件名
                                    fname, fcontent = generate_download_file(original_record, table_name)

                                    if fcontent:
                                        zip_file.writestr(fname, fcontent)
                                        file_count += 1

                            zip_buffer.seek(0)
                            if file_count > 0:
                                st.success(f"成功打包 {file_count} 个文件！")
                                st.download_button(
                                    label="⬇️ 点击下载 ZIP压缩包",
                                    data=zip_buffer,
                                    file_name="hirf_data_batch.zip",
                                    mime="application/zip"
                                )
                            else:
                                st.warning("选中的记录数据为空。")

            st.markdown("---")

            # --- D. 单条详情查看与增强绘图 ---
            st.subheader("详细数据视图 (单条查看)")

            # 建立 ID -> 机型 映射
            id_map = {r['id']: r['aircraft_model'] for r in st.session_state.records}

            selected_id = st.selectbox(
                "选择ID查看详情",
                [r['id'] for r in st.session_state.records],
                format_func=lambda x: f"ID: {x} | 机型: {id_map.get(x, '未知')}"
            )

            if selected_id:
                rec = next(r for r in st.session_state.records if r['id'] == selected_id)

                # 显示基础信息
                c1, c2 = st.columns(2)
                pos_key = 'current_probe_position' if not is_field_db else 'receiving_antenna_position'
                with c1:
                    st.write(f"**型号**: {rec['aircraft_model']}")
                    st.write(f"**{probe_label}**: {rec[pos_key]}")
                    if is_field_db:
                        st.write(f"**数据类型**: {rec.get('data_stat_type', 'N/A')}")
                with c2:
                    st.write(f"**天线位置**: {rec['antenna_position']}")
                    st.write(f"**极化**: {rec['antenna_polarization']}")

                # --- 增强绘图区域 ---
                data_content = rec['data_content']
                if data_content:
                    try:
                        # 解析数据
                        data = pd.read_csv(StringIO(data_content), sep='\t' if '\t' in data_content else ',',
                                           header=None)
                        x_data = pd.to_numeric(data.iloc[:, 0], errors='coerce')
                        y_data = pd.to_numeric(data.iloc[:, 1], errors='coerce')
                        mask = x_data.notna() & y_data.notna()
                        x_clean = x_data[mask]
                        y_clean = y_data[mask]

                        if not x_clean.empty:
                            st.markdown("#### 波形显示设置")
                            col_opt1, col_opt2 = st.columns([1, 2])

                            # 选项1: 线性 vs 对数
                            with col_opt1:
                                plot_scale = st.radio("显示模式", ["线性显示", "对数显示 (dB)"], horizontal=True)

                            # 选项2: 对数系数
                            log_factor = 20
                            with col_opt2:
                                if "对数" in plot_scale:
                                    log_option = st.selectbox("对数系数 (N * log10)", [20, 10, "自定义"])
                                    if log_option == "自定义":
                                        log_factor = st.number_input("输入系数", value=20.0)
                                    else:
                                        log_factor = log_option

                            # 绘图逻辑
                            fig, ax = plt.subplots(figsize=(10, 5))

                            if "对数" in plot_scale:
                                # dB 计算公式: N * log10(|y|)
                                y_array = np.array(y_clean)
                                eps = 1e-10  # 防止 log(0)
                                y_plot = log_factor * np.log10(np.abs(y_array) + eps)
                                ax.plot(x_clean, y_plot, color='tab:red', linewidth=1)
                                ylabel_suffix = f"(dB, N={log_factor})"
                            else:
                                ax.plot(x_clean, y_clean, color='tab:blue', linewidth=1)
                                ylabel_suffix = ""

                            ax.set_xlabel(f"Frequency ({rec.get('frequency_unit', 'MHz')})")
                            ax.set_ylabel(f"{ylabel} {ylabel_suffix}")
                            ax.set_title(f"{rec['aircraft_model']} - {rec[pos_key]}")
                            ax.grid(True, linestyle='--', alpha=0.6, which='both')
                            st.pyplot(fig)
                        else:
                            st.warning("数据解析为空，无法绘图。")
                    except Exception as e:
                        st.error(f"绘图出错: {e}")
                else:
                    st.warning("无数据内容。")

                # 单文件下载
                fname, fcontent = generate_download_file(rec, table_name)
                st.download_button("📥 下载该数据文件", fcontent, fname)

    # ================= 2. 添加数据 (含批量) =================
    elif operation == "添加数据":
        st.header(f"{database_type} - 添加")
        tab_single, tab_batch = st.tabs(["单条添加", "批量文件导入"])

        # --- 单条添加 ---
        with tab_single:
            with st.form("add_form"):
                col1, col2 = st.columns(2)
                with col1:
                    aircraft_model = st.text_input("飞机型号*", "")
                    probe_val = st.text_input(f"{probe_label}*", "")
                with col2:
                    antenna_pos = st.text_input("实验天线位置*", "")
                    f_units = ["Hz", "KHz", "MHz", "GHz"]
                    f_idx = 2 if not is_field_db else 3
                    freq_unit = st.selectbox("频率单位*", f_units, index=f_idx)

                col3, col4, col5 = st.columns(3)
                with col3:
                    ant_type = st.text_input("实验天线类型*", "一般天线")
                with col4:
                    ant_pol = st.selectbox("极化方式*", ["垂直极化", "水平极化"])
                with col5:
                    ant_angle = st.text_input("入射角度*", "0")

                data_stat_type = "MAX"
                if is_field_db:
                    st.markdown("---")
                    data_stat_type = st.selectbox("数据统计类型*", ["MAX", "MIN", "AV"])

                data_file = st.file_uploader("上传数据文件 (TXT)*", type=['txt'])
                notes = st.text_area("备注", "")

                if st.form_submit_button("提交单条数据"):
                    if not (aircraft_model and probe_val and antenna_pos and data_file):
                        st.error("请填写所有带 * 的必填项")
                    else:
                        content = parse_data_file(data_file)
                        if content:
                            valid, msg = validate_frequency_range(content, freq_unit, table_name)
                            if not valid:
                                st.error(f"校验失败: {msg}")
                            else:
                                record = {
                                    "aircraft_model": aircraft_model,
                                    "antenna_position": antenna_pos,
                                    "antenna_type": ant_type,
                                    "antenna_polarization": ant_pol,
                                    "antenna_incident_angle": ant_angle,
                                    "data_content": content,
                                    "frequency_unit": freq_unit,
                                    "notes": notes
                                }
                                if not is_field_db:
                                    record["current_probe_position"] = probe_val
                                else:
                                    record["receiving_antenna_position"] = probe_val
                                    record["data_stat_type"] = data_stat_type

                                if add_record_db(conn, table_name, record):
                                    st.success("数据添加成功！")

        # --- 批量导入 ---
        with tab_batch:
            st.markdown("### 批量数据文件导入")
            uploaded_files = st.file_uploader("选择多个数据文件", type=["txt", "dat"], accept_multiple_files=True)
            if uploaded_files:
                file_map = {f.name: f for f in uploaded_files}
                if st.session_state.batch_hirf_cache is None or len(st.session_state.batch_hirf_cache) != len(
                        uploaded_files):
                    data_list = []
                    for f in uploaded_files:
                        smart = smart_parse_hirf_filename(f.name)
                        row = {
                            "文件名": f.name,
                            "飞机型号": smart["aircraft_model"],
                            probe_label: smart["position"],
                            "实验天线位置": smart["antenna_pos"],
                            "极化方式": smart["polarization"],
                            "频率单位": "MHz" if not is_field_db else "MHz",
                            "备注": "批量导入"
                        }
                        if is_field_db:
                            row["数据类型"] = smart["type"]
                        data_list.append(row)
                    st.session_state.batch_hirf_cache = pd.DataFrame(data_list)

                df_batch = st.session_state.batch_hirf_cache
                col_config = {
                    "文件名": st.column_config.TextColumn("文件名", disabled=True),
                    "飞机型号": st.column_config.TextColumn(required=True),
                    probe_label: st.column_config.TextColumn(required=True),
                    "极化方式": st.column_config.SelectboxColumn(options=["垂直极化", "水平极化"], required=True),
                    "频率单位": st.column_config.SelectboxColumn(options=["Hz", "KHz", "MHz", "GHz"], required=True)
                }
                if is_field_db:
                    col_config["数据类型"] = st.column_config.SelectboxColumn(options=["MAX", "MIN", "AV"], required=True)

                st.markdown("⬇️ **请在下方表格确认并修正信息:**")
                edited_df = st.data_editor(df_batch, column_config=col_config, use_container_width=True,
                                           hide_index=True, num_rows="fixed")

                if st.button(f"确认导入 {len(uploaded_files)} 个文件", type="primary"):
                    success_count = 0
                    fail_count = 0
                    progress_bar = st.progress(0)
                    for idx, row in edited_df.iterrows():
                        fname = row["文件名"]
                        f_obj = file_map.get(fname)
                        if not row["飞机型号"] or not row[probe_label]:
                            fail_count += 1
                            continue
                        f_obj.seek(0)
                        content = parse_data_file(f_obj)
                        valid, msg = validate_frequency_range(content, row["频率单位"], table_name)
                        if not valid:
                            st.error(f"{fname}: {msg}")
                            fail_count += 1
                            continue
                        db_record = {
                            "aircraft_model": row["飞机型号"],
                            "antenna_position": row["实验天线位置"],
                            "antenna_type": "一般天线",
                            "antenna_polarization": row["极化方式"],
                            "antenna_incident_angle": "0",
                            "data_content": content,
                            "frequency_unit": row["频率单位"],
                            "notes": row["备注"]
                        }
                        if is_field_db:
                            db_record["receiving_antenna_position"] = row[probe_label]
                            db_record["data_stat_type"] = row["数据类型"]
                        else:
                            db_record["current_probe_position"] = row[probe_label]
                        if add_record_db(conn, table_name, db_record):
                            success_count += 1
                        else:
                            fail_count += 1
                        progress_bar.progress((idx + 1) / len(edited_df))

                    st.toast(f"导入完成! 成功: {success_count}, 失败: {fail_count}")
                    if success_count > 0:
                        st.success(f"成功导入 {success_count} 条数据")
                        st.session_state.batch_hirf_cache = None

    # ================= 3. 修改数据 =================
        # ================= 3. 修改数据 (已优化：字段全覆盖) =================
    elif operation == "修改数据":
        st.header(f"{database_type} - 修改")
        records = query_records(conn, table_name)

        if not records:
            st.warning("暂无数据可供修改")
        else:
            # 1. 建立 ID -> 机型 映射，方便搜索选择
            id_map = {r['id']: r['aircraft_model'] for r in records}

            # 使用带搜索功能的下拉框
            sel_id = st.selectbox(
                "选择要修改的记录",
                [r['id'] for r in records],
                format_func=lambda x: f"ID: {x} | 机型: {id_map.get(x, '未知')}"
            )

            # 获取当前选中的完整记录
            rec = next(r for r in records if r['id'] == sel_id)

            # 使用容器包裹表单，视觉更清晰
            with st.container(border=True):
                st.markdown(f"### 编辑记录 ID: {sel_id}")

                with st.form("update_form"):
                    # === 第一行：基础信息 ===
                    col1, col2 = st.columns(2)
                    with col1:
                        new_model = st.text_input("飞机型号*", value=rec['aircraft_model'])

                        # 根据表类型判断字段名
                        pos_key = 'current_probe_position' if not is_field_db else 'receiving_antenna_position'
                        new_pos = st.text_input(f"{probe_label}*", value=rec[pos_key])

                    with col2:
                        new_ant_pos = st.text_input("实验天线位置*", value=rec['antenna_position'])

                        # 频率单位处理
                        f_units = ["Hz", "KHz", "MHz", "GHz"]
                        curr_unit = rec.get('frequency_unit', 'MHz')
                        # 防止数据库中的单位不在列表中导致报错
                        unit_index = f_units.index(curr_unit) if curr_unit in f_units else 2
                        new_freq_unit = st.selectbox("频率单位*", f_units, index=unit_index)

                    # === 第二行：天线参数 ===
                    col3, col4, col5 = st.columns(3)
                    with col3:
                        new_ant_type = st.text_input("实验天线类型*", value=rec.get('antenna_type', '一般天线'))

                    with col4:
                        # 极化方式处理
                        pol_opts = ["垂直极化", "水平极化"]
                        curr_pol = rec.get('antenna_polarization', '垂直极化')
                        pol_idx = pol_opts.index(curr_pol) if curr_pol in pol_opts else 0
                        new_pol = st.selectbox("极化方式*", pol_opts, index=pol_idx)

                    with col5:
                        new_angle = st.text_input("入射角度*", value=rec.get('antenna_incident_angle', '0'))

                    # === 第三行：特殊字段 (仅感应电场) ===
                    new_stat_type = "MAX"
                    if is_field_db:
                        st.markdown("---")
                        stat_opts = ["MAX", "MIN", "AV"]
                        curr_stat = rec.get('data_stat_type', 'MAX')
                        stat_idx = stat_opts.index(curr_stat) if curr_stat in stat_opts else 0
                        new_stat_type = st.selectbox("数据统计类型*", stat_opts, index=stat_idx)

                    st.markdown("---")

                    # === 第四行：文件与备注 ===
                    st.markdown("**数据文件管理**")
                    col_file_info, col_file_up = st.columns([1, 2])
                    with col_file_info:
                        st.info("当前已存储数据。如需修改，请在右侧上传新文件；留空则保持原数据。")
                    with col_file_up:
                        new_data_file = st.file_uploader("替换数据文件 (可选)", type=['txt'])

                    new_notes = st.text_area("备注", value=rec.get('notes', ''))

                    # 提交按钮
                    submitted = st.form_submit_button("💾 保存修改", type="primary")

                # === 处理提交逻辑 ===
                if submitted:
                    if not (new_model and new_pos and new_ant_pos and new_ant_type):
                        st.error("带 * 的字段不能为空")
                    else:
                        try:
                            # 1. 确定数据内容 (使用新上传的 或 保持旧的)
                            final_content = rec['data_content']
                            if new_data_file is not None:
                                parsed_content = parse_data_file(new_data_file)
                                # 如果上传了新文件，必须重新校验频率范围
                                valid, msg = validate_frequency_range(parsed_content, new_freq_unit, table_name)
                                if not valid:
                                    st.error(f"新文件校验失败: {msg}")
                                    st.stop()  # 终止执行
                                else:
                                    final_content = parsed_content

                            # 2. 执行数据库更新
                            cursor = conn.cursor()

                            if is_field_db:
                                cursor.execute(f'''
                                        UPDATE {table_name} SET 
                                        aircraft_model=?, receiving_antenna_position=?, antenna_position=?, 
                                        antenna_type=?, antenna_polarization=?, antenna_incident_angle=?,
                                        frequency_unit=?, notes=?, data_stat_type=?, data_content=?
                                        WHERE id=?
                                    ''', (
                                    new_model, new_pos, new_ant_pos,
                                    new_ant_type, new_pol, new_angle,
                                    new_freq_unit, new_notes, new_stat_type, final_content,
                                    sel_id
                                ))
                            else:
                                cursor.execute(f'''
                                        UPDATE {table_name} SET 
                                        aircraft_model=?, current_probe_position=?, antenna_position=?, 
                                        antenna_type=?, antenna_polarization=?, antenna_incident_angle=?,
                                        frequency_unit=?, notes=?, data_content=?
                                        WHERE id=?
                                    ''', (
                                    new_model, new_pos, new_ant_pos,
                                    new_ant_type, new_pol, new_angle,
                                    new_freq_unit, new_notes, final_content,
                                    sel_id
                                ))

                            conn.commit()
                            st.toast("数据修改成功！", icon="✅")
                            time.sleep(1)  # 稍作延迟以显示提示
                            st.rerun()  # 刷新页面显示最新数据

                        except Exception as e:
                            st.error(f"更新失败: {e}")





    # ================= 4. 删除数据 (自动刷新) =================
    elif operation == "删除数据":
        st.header(f"{database_type} - 删除")
        records = query_records(conn, table_name)
        if records:
            # 1. 建立 ID -> 机型 映射
            id_map = {r['id']: r['aircraft_model'] for r in records}

            # 2. 选择框，使用 format_func
            sel_id = st.selectbox(
                "选择要删除的记录",
                [r['id'] for r in records],
                format_func=lambda x: f"ID: {x} | 机型: {id_map.get(x, '未知')}"
            )

            # 3. 提示信息
            to_delete_rec = next((r for r in records if r['id'] == sel_id), None)
            if to_delete_rec:
                st.warning(f"即将删除: 【{to_delete_rec['aircraft_model']}】 的数据 (ID: {sel_id})，此操作无法撤销！")

            # 4. 删除逻辑
            if st.button("确认删除", type="primary"):
                if delete_record(conn, table_name, sel_id):
                    # 显示 Toast 提示
                    st.toast(f"ID:{sel_id} 删除成功，正在刷新...", icon="🗑️")

                    # 清除本地缓存
                    st.session_state.records = []
                    st.session_state.selected_id = None

                    # 延时让用户看清提示
                    time.sleep(0.8)

                    # 强制刷新页面，更新下拉框
                    st.rerun()
        else:
            st.info("无数据可删")

    conn.close()


#if __name__ == "__main__":
main()