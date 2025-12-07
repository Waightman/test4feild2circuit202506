import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO
import wyz_io
import os
import re

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
            min_freq, max_freq = 0.2, 1400
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
    try:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM {table_name} WHERE id=?', (record_id,))
        conn.commit()
        st.success("记录删除成功!")
    except sqlite3.Error as e:
        st.error(f"删除记录错误: {e}")


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
        import wyz_io
        logo_base64 = wyz_io.image_to_base64(LOGO_PATH)
        logo_html = f"""
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
            <img src="data:image/jpeg;base64,{logo_base64}" alt="公司标徽" style="height: 60px;">
            <h3 style="margin: 0; font-size: 42px;">中航通飞华南飞机工业有限公司</h3>
        </div>
        """
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

    st.sidebar.title("导航")
    menu = ["感应电流数据库 (0.2MHz~1400MHz)", "感应电场数据库 (100MHz~8GHz)", "关于"]
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
    if operation == "查询数据":
        st.header(f"{database_type} - 查询")
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

        if st.session_state.records:
            df = pd.DataFrame(st.session_state.records)
            if 'data_content' in df.columns: df = df.drop(columns=['data_content'])
            st.dataframe(df, use_container_width=True)

            # 详情查看
            record_ids = [r['id'] for r in st.session_state.records]

            # --- 修改处：创建ID到模型名称的映射，并在下拉框中显示 ---
            record_map = {r['id']: r['aircraft_model'] for r in st.session_state.records}

            selected_id = st.selectbox(
                "选择ID查看详情",
                record_ids,
                format_func=lambda x: f"ID: {x} | 机型: {record_map.get(x, '未知')}"  # 使用 ID + 模型名称
            )
            # ----------------------------------------------------

            if selected_id:
                rec = next(r for r in st.session_state.records if r['id'] == selected_id)
                st.markdown("---")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**型号**: {rec['aircraft_model']}")
                    pos_key = 'current_probe_position' if not is_field_db else 'receiving_antenna_position'
                    st.write(f"**{probe_label}**: {rec[pos_key]}")
                    if is_field_db:
                        st.write(f"**数据类型**: {rec.get('data_stat_type', 'N/A')}")
                with c2:
                    st.write(f"**天线位置**: {rec['antenna_position']}")
                    st.write(f"**极化**: {rec['antenna_polarization']}")

                plot_data(rec['data_content'], f"{rec['aircraft_model']} - {rec[pos_key]}", ylabel)

                fname, fcontent = generate_download_file(rec, table_name)
                st.download_button("📥 下载数据文件", fcontent, fname)

    # ================= 2. 添加数据 (含批量导入) =================
    elif operation == "添加数据":
        st.header(f"{database_type} - 添加")
        tab_single, tab_batch = st.tabs(["单条添加", "批量文件导入"])

        # ... (添加数据逻辑保持不变)
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
                    data_stat_type = st.selectbox("数据统计类型 (Task 1)*", ["MAX", "MIN", "AV"], help="区分最大值、最小值或平均值数据")

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

        with tab_batch:
            st.markdown("### 批量数据文件导入")
            st.info(f"支持多文件上传。系统会根据文件名自动猜测型号、位置等信息。文件名示例: `AG600_Head_Ant1_Vertical.txt`")
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
                            "频率单位": "MHz" if not is_field_db else "GHz",
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

                st.markdown("⬇️ **请在下方表格确认并修正信息 (支持像Excel一样编辑):**")
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
                            st.toast(f"跳过 {fname}: 信息不完整", icon="⚠️")
                            fail_count += 1
                            continue
                        f_obj.seek(0)
                        content = parse_data_file(f_obj)
                        valid, msg = validate_frequency_range(content, row["频率单位"], table_name)
                        if not valid:
                            st.error(f"文件 {fname} 校验失败: {msg}")
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
    elif operation == "修改数据":
        st.header(f"{database_type} - 修改")
        records = query_records(conn, table_name)
        if not records:
            st.warning("暂无数据")
        else:
            # --- 修改处：创建ID到模型名称的映射，并在下拉框中显示 ---
            record_map = {r['id']: r['aircraft_model'] for r in records}
            sel_id = st.selectbox(
                "选择记录修改",
                [r['id'] for r in records],
                format_func=lambda x: f"ID: {x} | 机型: {record_map.get(x, '未知')}"  # 使用 ID + 模型名称
            )
            # ----------------------------------------------------

            rec = next(r for r in records if r['id'] == sel_id)

            with st.form("update_form"):
                c1, c2 = st.columns(2)
                new_model = c1.text_input("飞机型号", rec['aircraft_model'])
                pos_key = 'current_probe_position' if not is_field_db else 'receiving_antenna_position'
                new_pos = c1.text_input(probe_label, rec[pos_key])

                new_ant_pos = c2.text_input("天线位置", rec['antenna_position'])

                if is_field_db:
                    curr_type = rec.get('data_stat_type', 'MAX') or 'MAX'
                    idx_type = ["MAX", "MIN", "AV"].index(curr_type) if curr_type in ["MAX", "MIN", "AV"] else 0
                    new_type = c2.selectbox("数据类型", ["MAX", "MIN", "AV"], index=idx_type)

                submitted = st.form_submit_button("更新数据")

                if submitted:
                    cursor = conn.cursor()
                    if is_field_db:
                        cursor.execute(
                            f"UPDATE {table_name} SET aircraft_model=?, receiving_antenna_position=?, antenna_position=?, data_stat_type=? WHERE id=?",
                            (new_model, new_pos, new_ant_pos, new_type, sel_id))
                    else:
                        cursor.execute(
                            f"UPDATE {table_name} SET aircraft_model=?, current_probe_position=?, antenna_position=? WHERE id=?",
                            (new_model, new_pos, new_ant_pos, sel_id))
                    conn.commit()
                    st.success("更新成功！")

    # ================= 4. 删除数据 =================
    elif operation == "删除数据":
        st.header(f"{database_type} - 删除")
        records = query_records(conn, table_name)
        if records:
            # --- 修改处：创建ID到模型名称的映射，并在下拉框中显示 ---
            record_map = {r['id']: r['aircraft_model'] for r in records}
            sel_id = st.selectbox(
                "选择要删除的ID",
                [r['id'] for r in records],
                format_func=lambda x: f"ID: {x} | 机型: {record_map.get(x, '未知')}"  # 使用 ID + 模型名称
            )
            # ----------------------------------------------------

            if st.button("确认删除"):
                delete_record(conn, table_name, sel_id)
        else:
            st.info("无数据可删")

    conn.close()


#if __name__ == "__main__":
main()