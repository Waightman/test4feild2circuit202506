import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO
import os
import re
import zipfile
import numpy as np
import io
import time

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

        # --- 数据库迁移逻辑 1: 检查并添加 data_stat_type 字段 ---
        try:
            cursor.execute("SELECT data_stat_type FROM induced_field LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE induced_field ADD COLUMN data_stat_type TEXT DEFAULT 'MAX'")
            st.toast("数据库结构已更新：添加了 data_stat_type 字段", icon="✅")

        # --- 数据库迁移逻辑 2: 检查并添加 start_freq 和 stop_freq 字段 (新增) ---
        # 针对 induced_current 表
        try:
            cursor.execute("SELECT start_freq FROM induced_current LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE induced_current ADD COLUMN start_freq REAL DEFAULT 0")
            cursor.execute("ALTER TABLE induced_current ADD COLUMN stop_freq REAL DEFAULT 0")
            st.toast("数据库更新：感应电流表添加频率范围字段", icon="✅")

        # 针对 induced_field 表
        try:
            cursor.execute("SELECT start_freq FROM induced_field LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE induced_field ADD COLUMN start_freq REAL DEFAULT 0")
            cursor.execute("ALTER TABLE induced_field ADD COLUMN stop_freq REAL DEFAULT 0")
            st.toast("数据库更新：感应电场表添加频率范围字段", icon="✅")
        # -------------------------------------------------------------------

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
    # 高级批量导入缓存
    if 'adv_batch_hirf_cache' not in st.session_state:
        st.session_state.adv_batch_hirf_cache = None


def parse_data_file(uploaded_file):
    """解析上传的文件内容"""
    try:
        content = uploaded_file.getvalue().decode("utf-8", errors='ignore')
        return content
    except Exception as e:
        st.error(f"解析数据文件错误: {e}")
        return None


def calculate_freq_range(data_content):
    """从数据内容中计算起始和终止频率"""
    if not data_content:
        return 0.0, 0.0
    try:
        df = pd.read_csv(StringIO(data_content), sep='\t' if '\t' in data_content else ',', header=None)
        if df.shape[1] >= 1:
            # 尝试转换第一列为数字
            freqs = pd.to_numeric(df.iloc[:, 0], errors='coerce').dropna()
            if not freqs.empty:
                return float(freqs.min()), float(freqs.max())
    except Exception:
        pass
    return 0.0, 0.0


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
            min_freq, max_freq = 100, 18000
            data_type = "感应电磁"

        f_min = frequencies_mhz.min()
        f_max = frequencies_mhz.max()

        # 宽松一点的验证，避免边界误差
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
    """智能解析 HIRF 文件名 (新增：自动识别单位)"""
    info = {
        "aircraft_model": "",
        "position": "",
        "antenna_pos": "",
        "polarization": "垂直极化",
        "angle": "0",
        "type": "MAX",
        "unit": "MHz"  # 默认值
    }

    name_no_ext = filename.rsplit('.', 1)[0]

    # --- 单位自动识别逻辑 ---
    upper_name = name_no_ext.upper()
    if "GHZ" in upper_name:
        info["unit"] = "GHz"
    elif "MHZ" in upper_name:
        info["unit"] = "MHz"
    elif "KHZ" in upper_name:
        info["unit"] = "KHz"
    elif "HZ" in upper_name:
        info["unit"] = "Hz"
    # ---------------------------

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

        # 确保字典里有频率范围键，没有则补0
        record_dict.setdefault('start_freq', 0)
        record_dict.setdefault('stop_freq', 0)

        if table_name == "induced_current":
            cursor.execute(f'''
            INSERT INTO {table_name} 
            (aircraft_model, current_probe_position, antenna_position, antenna_type, 
             antenna_polarization, antenna_incident_angle, data_content, frequency_unit, 
             start_freq, stop_freq, notes)
            VALUES (:aircraft_model, :current_probe_position, :antenna_position, :antenna_type, 
             :antenna_polarization, :antenna_incident_angle, :data_content, :frequency_unit, 
             :start_freq, :stop_freq, :notes)
            ''', record_dict)
        else:
            cursor.execute(f'''
            INSERT INTO {table_name} 
            (aircraft_model, receiving_antenna_position, antenna_position, antenna_type, 
             antenna_polarization, antenna_incident_angle, data_content, frequency_unit, 
             start_freq, stop_freq, notes, data_stat_type)
            VALUES (:aircraft_model, :receiving_antenna_position, :antenna_position, :antenna_type, 
             :antenna_polarization, :antenna_incident_angle, :data_content, :frequency_unit, 
             :start_freq, :stop_freq, :notes, :data_stat_type)
            ''', record_dict)
        conn.commit()
        return True
    except sqlite3.Error as e:
        st.error(f"添加记录数据库错误: {e}")
        return False


def delete_record(conn, table_name, record_id):
    """删除记录"""
    try:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM {table_name} WHERE id=?', (record_id,))
        conn.commit()
        return True
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
    menu = ["感应电流数据库 (0.5MHz~400MHz)", "感应电场数据库 (100MHz~18GHz)", "关于"]
    database_type = st.sidebar.selectbox("数据库选择", menu)

    if 'prev_database_type' not in st.session_state:
        st.session_state.prev_database_type = database_type
    elif st.session_state.prev_database_type != database_type:
        st.session_state.records = []
        st.session_state.selected_id = None
        st.session_state.batch_hirf_cache = None
        st.session_state.adv_batch_hirf_cache = None
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

    # 【Bug 3 修复】切换操作页面时，清空之前页面的列表缓存，确保每次进入新页面看到最新数据库状态
    if 'prev_operation' not in st.session_state:
        st.session_state.prev_operation = operation
    elif st.session_state.prev_operation != operation:
        st.session_state.records = []
        if 'delete_records_induced_current' in st.session_state:
            del st.session_state['delete_records_induced_current']
        if 'delete_records_induced_field' in st.session_state:
            del st.session_state['delete_records_induced_field']
        st.session_state.prev_operation = operation

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

            df_display = df_origin.copy()
            if 'data_content' in df_display.columns:
                df_display = df_display.drop(columns=['data_content'])
            df_display.insert(0, "选择", False)

            st.markdown("### 📊 数据列表 (请勾选需要下载的数据)")

            edited_df = st.data_editor(
                df_display,
                column_config={
                    "选择": st.column_config.CheckboxColumn("选择", help="勾选以加入批量下载", default=False),
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "aircraft_model": st.column_config.TextColumn("飞机型号", disabled=True),
                    "start_freq": st.column_config.NumberColumn("起始频率", format="%.2f", disabled=True),
                    "stop_freq": st.column_config.NumberColumn("终止频率", format="%.2f", disabled=True),
                    "frequency_unit": st.column_config.TextColumn("单位", disabled=True),
                },
                disabled=["id", "aircraft_model", "current_probe_position", "receiving_antenna_position"],
                hide_index=True,
                use_container_width=True
            )

            selected_rows = edited_df[edited_df["选择"] == True]

            with st.expander("📦 批量下载操作区", expanded=True):
                col_btn, col_info = st.columns([1, 2])
                with col_info:
                    st.info(f"当前筛选结果共 {len(df_origin)} 条，您已勾选 **{len(selected_rows)}** 条。")

                with col_btn:
                    # 【Bug 1 修复】移除外层容易导致闪退的 st.button 嵌套
                    if not selected_rows.empty:
                        zip_buffer = io.BytesIO()
                        file_count = 0

                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            for index, row in selected_rows.iterrows():
                                original_record = df_origin[df_origin['id'] == row['id']].iloc[0]
                                fname, fcontent = generate_download_file(original_record, table_name)

                                if fcontent:
                                    zip_file.writestr(fname, fcontent)
                                    file_count += 1

                        zip_buffer.seek(0)
                        if file_count > 0:
                            st.download_button(
                                label=f"⬇️ 打包下载已选的 {file_count} 个文件 (ZIP)",
                                data=zip_buffer,
                                file_name="hirf_data_batch.zip",
                                mime="application/zip",
                                type="primary"
                            )
                    else:
                        st.button("请先在上方表格中勾选数据", disabled=True)

            st.markdown("---")
            st.subheader("详细数据视图 (单条查看)")

            id_map = {r['id']: r['aircraft_model'] for r in st.session_state.records}

            selected_id = st.selectbox(
                "选择ID查看详情",
                [r['id'] for r in st.session_state.records],
                format_func=lambda x: f"ID: {x} | 机型: {id_map.get(x, '未知')}"
            )

            if selected_id:
                rec = next(r for r in st.session_state.records if r['id'] == selected_id)

                c1, c2 = st.columns(2)
                pos_key = 'current_probe_position' if not is_field_db else 'receiving_antenna_position'
                with c1:
                    st.write(f"**型号**: {rec['aircraft_model']}")
                    st.write(f"**{probe_label}**: {rec[pos_key]}")
                    st.write(
                        f"**频率范围**: {rec.get('start_freq', 0)} - {rec.get('stop_freq', 0)} {rec.get('frequency_unit', '')}")
                    if is_field_db:
                        st.write(f"**数据类型**: {rec.get('data_stat_type', 'N/A')}")
                with c2:
                    st.write(f"**天线位置**: {rec['antenna_position']}")
                    st.write(f"**极化**: {rec['antenna_polarization']}")

                data_content = rec['data_content']
                if data_content:
                    try:
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

                            with col_opt1:
                                plot_scale = st.radio("显示模式", ["线性显示", "对数显示 (dB)"], horizontal=True)

                            log_factor = 20
                            with col_opt2:
                                if "对数" in plot_scale:
                                    log_option = st.selectbox("对数系数 (N * log10)", [20, 10, "自定义"])
                                    if log_option == "自定义":
                                        log_factor = st.number_input("输入系数", value=20.0)
                                    else:
                                        log_factor = log_option

                            fig, ax = plt.subplots(figsize=(10, 5))

                            if "对数" in plot_scale:
                                y_array = np.array(y_clean)
                                eps = 1e-10
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

                fname, fcontent = generate_download_file(rec, table_name)
                st.download_button("📥 下载该数据文件", fcontent, fname)

    # ================= 2. 添加数据 (含批量) =================
    elif operation == "添加数据":
        st.header(f"{database_type} - 添加")
        tab_single, tab_batch, tab_adv_batch = st.tabs(["单条添加", "普通批量导入", "高级批量导入(文件名提取)"])

        # --- 单条添加 ---
        with tab_single:
            st.markdown("### 📝 单条数据录入")

            uploaded_file = st.file_uploader("📂 第一步：上传数据文件以自动识别字段", type=['txt', 'dat'], key="single_file_up")

            parsed_info = {
                "aircraft_model": "",
                "position": "",
                "antenna_pos": "",
                "polarization": "垂直极化",
                "angle": "0",
                "type": "MAX",
                "unit": "MHz"
            }

            calc_start, calc_stop = 0.0, 0.0

            if uploaded_file:
                parsed_info = smart_parse_hirf_filename(uploaded_file.name)
                temp_content = parse_data_file(uploaded_file)
                calc_start, calc_stop = calculate_freq_range(temp_content)
                st.toast(f"已识别: {uploaded_file.name} (单位:{parsed_info['unit']})", icon="🔍")

            with st.form("add_form_smart"):
                st.markdown("#### 第二步：确认并完善表单信息")

                col1, col2 = st.columns(2)
                with col1:
                    aircraft_model = st.text_input("1. 飞机型号*", value=parsed_info["aircraft_model"])
                    probe_val = st.text_input(f"2. {probe_label}*", value=parsed_info["position"])

                    if is_field_db:
                        stat_opts = ["MAX", "MIN", "AV"]
                        stat_idx = stat_opts.index(parsed_info["type"]) if parsed_info["type"] in stat_opts else 0
                        data_stat_type = st.selectbox("3. 数据类型*", stat_opts, index=stat_idx)

                    idx_offset = 1 if is_field_db else 0
                    antenna_pos = st.text_input(f"{3 + idx_offset}. 实验天线位置*", value=parsed_info["antenna_pos"])
                    ant_type = st.text_input(f"{4 + idx_offset}. 实验天线类型*", "一般天线")

                with col2:
                    pol_opts = ["垂直极化", "水平极化"]
                    pol_idx = pol_opts.index(parsed_info["polarization"]) if parsed_info[
                                                                                 "polarization"] in pol_opts else 0
                    ant_pol = st.selectbox(f"{5 + idx_offset}. 极化方式*", pol_opts, index=pol_idx)

                    ant_angle = st.text_input(f"{6 + idx_offset}. 入射角度*", value=parsed_info["angle"])

                    f_units = ["Hz", "KHz", "MHz", "GHz"]
                    default_unit_idx = 2
                    if parsed_info["unit"] in f_units:
                        default_unit_idx = f_units.index(parsed_info["unit"])
                    freq_unit = st.selectbox(f"{7 + idx_offset}. 频率单位*", f_units, index=default_unit_idx)

                st.markdown("---")
                st.caption("自动从文件数据计算的频率范围：")
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    in_start_freq = st.number_input("起始频率 (Num)", value=calc_start if uploaded_file else 0.0,
                                                    format="%.2f")
                with col_f2:
                    in_stop_freq = st.number_input("终止频率 (Num)", value=calc_stop if uploaded_file else 0.0,
                                                   format="%.2f")

                notes = st.text_area("备注", value="文件名识别导入" if uploaded_file else "")

                if st.form_submit_button("🚀 确认添加该条数据", type="primary"):
                    if not (aircraft_model and probe_val and antenna_pos and uploaded_file):
                        st.error("请确保已上传文件并填写所有带 * 的必填项")
                    else:
                        content = parse_data_file(uploaded_file)
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
                                    "start_freq": in_start_freq,
                                    "stop_freq": in_stop_freq,
                                    "notes": notes
                                }
                                if not is_field_db:
                                    record["current_probe_position"] = probe_val
                                else:
                                    record["receiving_antenna_position"] = probe_val
                                    record["data_stat_type"] = data_stat_type

                                if add_record_db(conn, table_name, record):
                                    st.success("数据添加成功！")
                                    time.sleep(1)
                                    st.rerun()

        # --- 普通批量导入 ---
        with tab_batch:
            st.markdown("### 普通批量数据文件导入")
            st.info("提示：批量导入默认设置天线类型为'一般天线'，入射角为'0'，其他将由文件名智能识别。")

            uploaded_files = st.file_uploader("选择多个数据文件", type=["txt", "dat"], accept_multiple_files=True)

            if uploaded_files:
                file_map = {f.name: f for f in uploaded_files}

                if st.session_state.batch_hirf_cache is None or len(st.session_state.batch_hirf_cache) != len(
                        uploaded_files):
                    data_list = []
                    for f in uploaded_files:
                        smart = smart_parse_hirf_filename(f.name)
                        f.seek(0)
                        c_temp = parse_data_file(f)
                        s_freq, e_freq = calculate_freq_range(c_temp)

                        row = {
                            "文件名": f.name,
                            "飞机型号": smart["aircraft_model"],
                            probe_label: smart["position"],
                            "实验天线位置": smart["antenna_pos"],
                            "天线类型": "一般天线",
                            "极化方式": smart["polarization"],
                            "天线入射角": smart["angle"],
                            "频率单位": smart["unit"],
                            "起始频率": s_freq,
                            "终止频率": e_freq,
                            "备注": "批量导入"
                        }
                        if is_field_db:
                            row["数据类型"] = smart["type"]
                        data_list.append(row)
                    st.session_state.batch_hirf_cache = pd.DataFrame(data_list)

                df_batch = st.session_state.batch_hirf_cache

                col_config = {
                    "文件名": st.column_config.TextColumn("文件名", disabled=True),
                    "飞机型号": st.column_config.TextColumn("飞机型号", required=True),
                    probe_label: st.column_config.TextColumn(probe_label, required=True),
                    "实验天线位置": st.column_config.TextColumn("实验天线位置", required=True),
                    "天线类型": st.column_config.TextColumn("天线类型", required=True),
                    "天线入射角": st.column_config.TextColumn("天线入射角", required=True),
                    "极化方式": st.column_config.SelectboxColumn("极化方式", options=["垂直极化", "水平极化"], required=True),
                    "频率单位": st.column_config.SelectboxColumn("频率单位", options=["Hz", "KHz", "MHz", "GHz"],
                                                             required=True),
                    "起始频率": st.column_config.NumberColumn("起始频率", format="%.2f", required=True),
                    "终止频率": st.column_config.NumberColumn("终止频率", format="%.2f", required=True),
                    "备注": st.column_config.TextColumn("备注")
                }

                if is_field_db:
                    col_config["数据类型"] = st.column_config.SelectboxColumn("数据类型", options=["MAX", "MIN", "AV"],
                                                                          required=True)

                st.markdown("⬇️ **请在下方表格确认并修正信息 (支持像Excel一样编辑):**")

                edited_df = st.data_editor(
                    df_batch,
                    column_config=col_config,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed"
                )

                if st.button(f"确认导入 {len(uploaded_files)} 个文件", type="primary", key="batch_btn_normal"):
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
                            "antenna_type": row["天线类型"],
                            "antenna_polarization": row["极化方式"],
                            "antenna_incident_angle": row["天线入射角"],
                            "data_content": content,
                            "frequency_unit": row["频率单位"],
                            "start_freq": row["起始频率"],
                            "stop_freq": row["终止频率"],
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
                        time.sleep(1.5)
                        st.rerun()

        # --- 高级批量导入 ---
        with tab_adv_batch:
            st.markdown("### 🛠️ 高级批量导入 (共同字段设置 + 文件名按序提取)")
            st.info(
                "在此统一设置本批次数据的 **共同字段**。对于留空或选择【从文件名提取】的字段，程序将严格按照您规定的字段顺序，"
                "将文件名以 `_` 拆分并对应填入。"
            )
            # --- 新增：动态显示字段顺序说明 ---
            if is_field_db:
                st.success("""
                            **📌 当前【感应电场数据库】的文件名提取顺序严格如下（以 `_` 分隔）：** `1.飞机型号` _ `2.接收天线位置` _ `3.数据类型` _ `4.实验天线位置` _ `5.实验天线类型` _ `6.极化方式` _ `7.入射角度` _ `8.频率单位`  
                            👉 *示例文件名：`机型A_雷达罩_MAX_机背_一般天线_垂直极化_0_MHz.txt`*
                            """)
            else:
                st.success("""
                            **📌 当前【感应电流数据库】的文件名提取顺序严格如下（以 `_` 分隔）：** `1.飞机型号` _ `2.电流探针位置` _ `3.实验天线位置` _ `4.实验天线类型` _ `5.极化方式` _ `6.入射角度` _ `7.频率单位`  
                            👉 *示例文件名：`机型A_线缆X_机背_一般天线_垂直极化_0_MHz.txt`*
                            """)
            # -----------------------------------
            with st.container(border=True):
                colA, colB = st.columns(2)
                with colA:
                    adv_model = st.text_input("飞机型号", placeholder="留空则从文件名提取", key="adv_mod")
                    adv_probe = st.text_input(probe_label, placeholder="留空则从文件名提取", key="adv_prob")
                    if is_field_db:
                        adv_stat = st.selectbox("数据类型", ["从文件名提取", "MAX", "MIN", "AV"], key="adv_st")
                    adv_ant_pos = st.text_input("实验天线位置", placeholder="留空则从文件名提取", key="adv_apos")
                with colB:
                    adv_ant_type = st.text_input("实验天线类型", placeholder="留空则从文件名提取", key="adv_atyp")
                    adv_pol = st.selectbox("极化方式", ["从文件名提取", "垂直极化", "水平极化"], key="adv_pol")
                    adv_angle = st.text_input("入射角度", placeholder="留空则从文件名提取", key="adv_ang")
                    adv_unit = st.selectbox("频率单位", ["从文件名提取", "Hz", "KHz", "MHz", "GHz"], key="adv_u")

            adv_files = st.file_uploader("选择多个待导入数据文件", type=["txt", "dat"], accept_multiple_files=True,
                                         key="adv_files")

            if adv_files:
                file_map_adv = {f.name: f for f in adv_files}
                st.caption("💡 说明：因为要读取文件自动生成频率范围，防止页面卡顿，目前采用手动生成预览表的方式。")

                if st.button("🔄 生成数据提取预览表", type="secondary"):
                    data_list_adv = []

                    if is_field_db:
                        ordered_fields = [
                            ("飞机型号", adv_model, ""),
                            (probe_label, adv_probe, ""),
                            ("数据类型", adv_stat, "从文件名提取"),
                            ("实验天线位置", adv_ant_pos, ""),
                            ("天线类型", adv_ant_type, ""),
                            ("极化方式", adv_pol, "从文件名提取"),
                            ("天线入射角", adv_angle, ""),
                            ("频率单位", adv_unit, "从文件名提取")
                        ]
                    else:
                        ordered_fields = [
                            ("飞机型号", adv_model, ""),
                            (probe_label, adv_probe, ""),
                            ("实验天线位置", adv_ant_pos, ""),
                            ("天线类型", adv_ant_type, ""),
                            ("极化方式", adv_pol, "从文件名提取"),
                            ("天线入射角", adv_angle, ""),
                            ("频率单位", adv_unit, "从文件名提取")
                        ]

                    for f in adv_files:
                        f.seek(0)
                        c_temp = parse_data_file(f)
                        s_freq, e_freq = calculate_freq_range(c_temp)

                        name_no_ext = f.name.rsplit('.', 1)[0]
                        parts = name_no_ext.split('_')
                        part_idx = 0

                        row = {"文件名": f.name}

                        for field_name, user_val, default_empty in ordered_fields:
                            if user_val == default_empty or str(user_val).strip() == "":
                                if part_idx < len(parts):
                                    row[field_name] = parts[part_idx]
                                    part_idx += 1
                                else:
                                    row[field_name] = ""
                            else:
                                row[field_name] = user_val

                        row["起始频率"] = s_freq
                        row["终止频率"] = e_freq
                        row["备注"] = "高级混合导入"

                        if row["极化方式"] not in ["垂直极化", "水平极化"]: row["极化方式"] = "垂直极化"
                        if row["频率单位"] not in ["Hz", "KHz", "MHz", "GHz"]: row["频率单位"] = "MHz"
                        if is_field_db and row["数据类型"] not in ["MAX", "MIN", "AV"]: row["数据类型"] = "MAX"

                        data_list_adv.append(row)

                    st.session_state.adv_batch_hirf_cache = pd.DataFrame(data_list_adv)

                if st.session_state.adv_batch_hirf_cache is not None:
                    df_adv_batch = st.session_state.adv_batch_hirf_cache

                    adv_col_config = {
                        "文件名": st.column_config.TextColumn("文件名", disabled=True),
                        "飞机型号": st.column_config.TextColumn("飞机型号", required=True),
                        probe_label: st.column_config.TextColumn(probe_label, required=True),
                        "实验天线位置": st.column_config.TextColumn("实验天线位置", required=True),
                        "天线类型": st.column_config.TextColumn("天线类型", required=True),
                        "天线入射角": st.column_config.TextColumn("天线入射角", required=True),
                        "极化方式": st.column_config.SelectboxColumn("极化方式", options=["垂直极化", "水平极化"], required=True),
                        "频率单位": st.column_config.SelectboxColumn("频率单位", options=["Hz", "KHz", "MHz", "GHz"],
                                                                 required=True),
                        "起始频率": st.column_config.NumberColumn("起始频率", format="%.2f", required=True),
                        "终止频率": st.column_config.NumberColumn("终止频率", format="%.2f", required=True),
                        "备注": st.column_config.TextColumn("备注")
                    }
                    if is_field_db:
                        adv_col_config["数据类型"] = st.column_config.SelectboxColumn("数据类型", options=["MAX", "MIN", "AV"],
                                                                                  required=True)

                    st.markdown("⬇️ **请仔细核对提取结果 (支持双击单元格手动修改):**")
                    adv_edited_df = st.data_editor(
                        df_adv_batch,
                        column_config=adv_col_config,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        key="adv_data_editor"
                    )

                    if st.button(f"🚀 确认导入 {len(adv_files)} 个文件", type="primary", key="batch_btn_adv"):
                        suc_count = 0
                        err_count = 0
                        pb = st.progress(0)

                        for idx, row in adv_edited_df.iterrows():
                            fname = row["文件名"]
                            f_obj = file_map_adv.get(fname)

                            if not row["飞机型号"] or not row[probe_label]:
                                err_count += 1
                                continue

                            f_obj.seek(0)
                            content = parse_data_file(f_obj)

                            valid, msg = validate_frequency_range(content, row["频率单位"], table_name)
                            if not valid:
                                st.error(f"{fname}: {msg}")
                                err_count += 1
                                continue

                            db_record = {
                                "aircraft_model": row["飞机型号"],
                                "antenna_position": row["实验天线位置"],
                                "antenna_type": row["天线类型"],
                                "antenna_polarization": row["极化方式"],
                                "antenna_incident_angle": row["天线入射角"],
                                "data_content": content,
                                "frequency_unit": row["频率单位"],
                                "start_freq": row["起始频率"],
                                "stop_freq": row["终止频率"],
                                "notes": row["备注"]
                            }

                            if is_field_db:
                                db_record["receiving_antenna_position"] = row[probe_label]
                                db_record["data_stat_type"] = row["数据类型"]
                            else:
                                db_record["current_probe_position"] = row[probe_label]

                            if add_record_db(conn, table_name, db_record):
                                suc_count += 1
                            else:
                                err_count += 1

                            pb.progress((idx + 1) / len(adv_edited_df))

                        st.toast(f"高级导入完成! 成功: {suc_count}, 失败: {err_count}")
                        if suc_count > 0:
                            st.success(f"成功混合提取并导入 {suc_count} 条数据")
                            st.session_state.adv_batch_hirf_cache = None
                            time.sleep(1.5)
                            st.rerun()

    # ================= 3. 修改数据 =================
    elif operation == "修改数据":
        st.header(f"{database_type} - 修改")
        records = query_records(conn, table_name)

        if not records:
            st.warning("暂无数据可供修改")
        else:
            id_map = {r['id']: r['aircraft_model'] for r in records}

            sel_id = st.selectbox(
                "选择要修改的记录",
                [r['id'] for r in records],
                format_func=lambda x: f"ID: {x} | 机型: {id_map.get(x, '未知')}"
            )

            rec = next(r for r in records if r['id'] == sel_id)

            with st.container(border=True):
                st.markdown(f"### 编辑记录 ID: {sel_id}")

                with st.form("update_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_model = st.text_input("飞机型号*", value=rec['aircraft_model'])
                        pos_key = 'current_probe_position' if not is_field_db else 'receiving_antenna_position'
                        new_pos = st.text_input(f"{probe_label}*", value=rec[pos_key])

                    with col2:
                        new_ant_pos = st.text_input("实验天线位置*", value=rec['antenna_position'])
                        f_units = ["Hz", "KHz", "MHz", "GHz"]
                        curr_unit = rec.get('frequency_unit', 'MHz')
                        unit_index = f_units.index(curr_unit) if curr_unit in f_units else 2
                        new_freq_unit = st.selectbox("频率单位*", f_units, index=unit_index)

                    col3, col4, col5 = st.columns(3)
                    with col3:
                        new_ant_type = st.text_input("实验天线类型*", value=rec.get('antenna_type', '一般天线'))
                    with col4:
                        pol_opts = ["垂直极化", "水平极化"]
                        curr_pol = rec.get('antenna_polarization', '垂直极化')
                        pol_idx = pol_opts.index(curr_pol) if curr_pol in pol_opts else 0
                        new_pol = st.selectbox("极化方式*", pol_opts, index=pol_idx)
                    with col5:
                        new_angle = st.text_input("入射角度*", value=rec.get('antenna_incident_angle', '0'))

                    st.markdown("**频率范围**")
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        new_start_f = st.number_input("起始频率", value=rec.get('start_freq', 0.0), format="%.2f")
                    with col_f2:
                        new_stop_f = st.number_input("终止频率", value=rec.get('stop_freq', 0.0), format="%.2f")

                    new_stat_type = "MAX"
                    if is_field_db:
                        st.markdown("---")
                        stat_opts = ["MAX", "MIN", "AV"]
                        curr_stat = rec.get('data_stat_type', 'MAX')
                        stat_idx = stat_opts.index(curr_stat) if curr_stat in stat_opts else 0
                        new_stat_type = st.selectbox("数据统计类型*", stat_opts, index=stat_idx)

                    st.markdown("---")

                    st.markdown("**数据文件管理**")
                    col_file_info, col_file_up = st.columns([1, 2])
                    with col_file_info:
                        st.info("如需修改数据，请上传新文件，否则将保留原数据。")
                    with col_file_up:
                        new_data_file = st.file_uploader("替换数据文件 (可选)", type=['txt'])

                    new_notes = st.text_area("备注", value=rec.get('notes', ''))

                    submitted = st.form_submit_button("💾 保存修改", type="primary")

                if submitted:
                    if not (new_model and new_pos and new_ant_pos and new_ant_type):
                        st.error("带 * 的字段不能为空")
                    else:
                        try:
                            final_content = rec['data_content']
                            if new_data_file is not None:
                                parsed_content = parse_data_file(new_data_file)
                                valid, msg = validate_frequency_range(parsed_content, new_freq_unit, table_name)
                                if not valid:
                                    st.error(f"新文件校验失败: {msg}")
                                    st.stop()
                                else:
                                    final_content = parsed_content
                                    # 【Bug 2 修复】：重新计算新文件的频率并覆盖旧值
                                    new_start_f, new_stop_f = calculate_freq_range(final_content)

                            cursor = conn.cursor()

                            if is_field_db:
                                cursor.execute(f'''
                                        UPDATE {table_name} SET 
                                        aircraft_model=?, receiving_antenna_position=?, antenna_position=?, 
                                        antenna_type=?, antenna_polarization=?, antenna_incident_angle=?,
                                        frequency_unit=?, notes=?, data_stat_type=?, data_content=?,
                                        start_freq=?, stop_freq=?
                                        WHERE id=?
                                    ''', (
                                    new_model, new_pos, new_ant_pos,
                                    new_ant_type, new_pol, new_angle,
                                    new_freq_unit, new_notes, new_stat_type, final_content,
                                    new_start_f, new_stop_f,
                                    sel_id
                                ))
                            else:
                                cursor.execute(f'''
                                        UPDATE {table_name} SET 
                                        aircraft_model=?, current_probe_position=?, antenna_position=?, 
                                        antenna_type=?, antenna_polarization=?, antenna_incident_angle=?,
                                        frequency_unit=?, notes=?, data_content=?,
                                        start_freq=?, stop_freq=?
                                        WHERE id=?
                                    ''', (
                                    new_model, new_pos, new_ant_pos,
                                    new_ant_type, new_pol, new_angle,
                                    new_freq_unit, new_notes, final_content,
                                    new_start_f, new_stop_f,
                                    sel_id
                                ))

                            conn.commit()
                            st.toast("数据修改成功！", icon="✅")
                            time.sleep(1)
                            st.rerun()

                        except Exception as e:
                            st.error(f"更新失败: {e}")

    # ================= 4. 删除数据 =================
    # ================= 4. 删除数据 =================
    elif operation == "删除数据":
        st.header(f"{database_type} - 删除")

        cache_key = f'delete_records_{table_name}'

        if cache_key not in st.session_state:
            st.session_state[cache_key] = []

        # --- A. 查询条件输入区域 ---
        col1, col2, col3 = st.columns(3)
        with col1:
            aircraft_model = st.text_input("飞机型号", key="del_model")
        with col2:
            probe_field = st.text_input(probe_label, key="del_probe")
        with col3:
            if is_field_db:
                data_stat = st.selectbox("数据类型", ["全部", "MAX", "MIN", "AV"], key="del_stat")
            else:
                data_stat = None

        # --- B. 执行查询 ---
        if st.button("🔍 查询待删除数据", key="del_search_btn"):
            cond = {}
            if aircraft_model: cond["aircraft_model"] = aircraft_model
            if probe_field:
                key = "current_probe_position" if not is_field_db else "receiving_antenna_position"
                cond[key] = probe_field
            if is_field_db and data_stat and data_stat != "全部":
                cond["data_stat_type"] = data_stat

            st.session_state[cache_key] = query_records(conn, table_name, cond)

        # --- C. 结果显示与批量删除 ---
        records = st.session_state.get(cache_key, [])
        if records:
            df_origin = pd.DataFrame(records)

            df_display = df_origin.copy()
            if 'data_content' in df_display.columns:
                df_display = df_display.drop(columns=['data_content'])
            df_display.insert(0, "选择", False)

            st.markdown("### 🗑️ 数据列表 (请勾选需要删除的数据)")

            disabled_cols = df_display.columns.tolist()
            disabled_cols.remove("选择")

            editor_key = f"delete_data_editor_{table_name}"

            # 渲染表格并获取编辑后的结果
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "选择": st.column_config.CheckboxColumn("选择", help="勾选以删除", default=False),
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "aircraft_model": st.column_config.TextColumn("飞机型号", disabled=True),
                    "start_freq": st.column_config.NumberColumn("起始频率", format="%.2f", disabled=True),
                    "stop_freq": st.column_config.NumberColumn("终止频率", format="%.2f", disabled=True),
                    "frequency_unit": st.column_config.TextColumn("单位", disabled=True),
                },
                disabled=disabled_cols,
                hide_index=True,
                use_container_width=True,
                key=editor_key
            )

            # 实时计算选中的行数
            selected_rows = edited_df[edited_df["选择"] == True]
            num_selected = len(selected_rows)

            # --- D. 改进的操作区：按钮在左侧且动态禁用 ---
            with st.expander("⚠️ 批量删除操作区", expanded=True):
                col_btn, col_info = st.columns([1, 2])  # 按钮在左侧

                with col_btn:
                    # 关键修改：增加 disabled 参数，根据选中数量判断
                    if st.button(
                            f"🚨 确认删除 ({num_selected})",
                            type="primary",
                            use_container_width=True,
                            disabled=(num_selected == 0)  # 核心逻辑：没勾选就置灰
                    ):
                        success_count = 0
                        for index, row in selected_rows.iterrows():
                            if delete_record(conn, table_name, row['id']):
                                success_count += 1

                        if success_count > 0:
                            st.success(f"成功删除 {success_count} 条数据！")
                            # 清理缓存确保刷新
                            st.session_state[cache_key] = query_records(conn, table_name)
                            if editor_key in st.session_state:
                                del st.session_state[editor_key]
                            time.sleep(1)
                            st.rerun()

                with col_info:
                    if num_selected > 0:
                        st.warning(f"注意：您已勾选 {num_selected} 条数据，删除后将无法恢复！")
                    else:
                        st.info(f"当前查询到 {len(df_origin)} 条记录。请在上方表格中勾选数据。")
        else:
            st.info("未查询到匹配的数据或数据库为空。")

    conn.close()


main()