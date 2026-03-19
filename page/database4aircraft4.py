import streamlit as st
import sqlite3
import os
import pandas as pd
from PIL import Image
import io
import time  # 新增: 用于表单提交后的短暂延迟刷新

# ================= 1. 配置与工具函数 =================

# 设置 Matplotlib 中文字体 (虽主要用于存图，但保持一致性)
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# 模拟 wyz_io
class MockWyzIo:
    @staticmethod
    def image_to_base64(path):
        import base64
        try:
            with open(path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode()
        except FileNotFoundError:
            return ""


try:
    import wyz_io
except ImportError:
    wyz_io = MockWyzIo()

DB_NAME = 'aircraft_hirf.db'


def create_connection():
    """创建数据库连接"""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库表结构 (包含自动升级逻辑)"""
    conn = create_connection()
    cursor = conn.cursor()

    # 1. HIRF 实验主表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hirf_experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aircraft_model TEXT NOT NULL,
        connector_number TEXT, 
        experiment_content TEXT, 
        test_method TEXT,
        frequency_range TEXT,
        field_strength TEXT,
        description TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # --- 数据库迁移: 检查并添加 test_method 字段 ---
    try:
        cursor.execute("SELECT test_method FROM hirf_experiments LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE hirf_experiments ADD COLUMN test_method TEXT")

    # --- 数据库迁移: 检查并添加 connector_number 字段 ---
    try:
        cursor.execute("SELECT connector_number FROM hirf_experiments LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE hirf_experiments ADD COLUMN connector_number TEXT")

    # --- 数据库迁移: 检查并添加 experiment_content 字段 ---
    try:
        cursor.execute("SELECT experiment_content FROM hirf_experiments LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE hirf_experiments ADD COLUMN experiment_content TEXT")

    # 2. HIRF 实验图片/数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hirf_experiment_images (
        img_id INTEGER PRIMARY KEY AUTOINCREMENT,
        exp_id INTEGER,
        image_name TEXT,
        image_desc TEXT,
        image_data BLOB,
        raw_data BLOB,
        raw_data_name TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (exp_id) REFERENCES hirf_experiments (id) ON DELETE CASCADE
    )
    ''')

    # --- 数据库迁移: 检查并添加 raw_data 相关字段 ---
    try:
        cursor.execute("SELECT raw_data FROM hirf_experiment_images LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE hirf_experiment_images ADD COLUMN raw_data BLOB")
        cursor.execute("ALTER TABLE hirf_experiment_images ADD COLUMN raw_data_name TEXT")

    conn.commit()
    conn.close()


# 初始化数据库
init_db()


# ================= 2. 功能模块实现 =================

def view_hirf_experiments():
    st.subheader("查看HIRF实验数据")

    # --- 搜索栏 ---
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            search_model = st.text_input("飞机型号", placeholder="如: AG600")
        with col2:
            search_connector = st.text_input("连接器编号", placeholder="如: J1201")
        with col3:
            search_content = st.selectbox("实验内容", ["所有", "LLSC", "LLSF"], index=0)
        with col4:
            search_method = st.selectbox("测试方法", ["所有", "BCI", "Direct Drive", "其他"], index=0)
        with col5:
            search_freq = st.text_input("频段", placeholder="如: 100MHz")

    # 初始化 session state
    if 'hirf_search_result' not in st.session_state:
        st.session_state['hirf_search_result'] = None

    if st.button("查询"):
        conn = create_connection()
        query = "SELECT * FROM hirf_experiments WHERE 1=1"
        params = []

        if search_model:
            query += " AND aircraft_model LIKE ?"
            params.append(f"%{search_model}%")

        if search_connector:
            query += " AND connector_number LIKE ?"
            params.append(f"%{search_connector}%")

        if search_content and search_content != "所有":
            query += " AND experiment_content = ?"
            params.append(search_content)

        if search_method and search_method != "所有":
            query += " AND test_method = ?"
            params.append(search_method)

        if search_freq:
            query += " AND frequency_range LIKE ?"
            params.append(f"%{search_freq}%")

        query += " ORDER BY upload_date DESC"

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        st.session_state['hirf_search_result'] = df

    # --- 结果展示 ---
    if st.session_state['hirf_search_result'] is not None:
        df = st.session_state['hirf_search_result']

        if df.empty:
            st.warning("没有找到匹配的记录")
        else:
            st.dataframe(
                df[['id', 'aircraft_model', 'connector_number', 'experiment_content', 'test_method', 'frequency_range',
                    'field_strength', 'upload_date']],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.subheader("📊 详细视图与图谱")

            selected_id = st.selectbox(
                "选择记录查看详情:",
                df['id'],
                format_func=lambda
                    x: f"ID:{x} | {df[df['id'] == x]['aircraft_model'].iloc[0]} - {df[df['id'] == x]['connector_number'].iloc[0] or 'No-Conn'}"
            )

            if selected_id:
                record = df[df['id'] == selected_id].iloc[0]

                # 1. 基础信息卡片
                with st.container(border=True):
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.markdown(f"**飞机型号:**\n{record['aircraft_model']}")
                    c2.markdown(f"**连接器编号:**\n{record['connector_number'] or '未填写'}")
                    c3.markdown(f"**实验内容:**\n{record['experiment_content'] or '未填写'}")
                    c4.markdown(f"**测试方法:**\n{record['test_method'] or '未填写'}")
                    c5.markdown(f"**频率范围:**\n{record['frequency_range']}")
                    c6.markdown(f"**场强等级:**\n{record['field_strength']}")
                    st.markdown(f"**实验综述:** {record['description'] or '无'}")

                # 2. 关联图片与原始数据
                conn = create_connection()
                img_df = pd.read_sql_query(
                    "SELECT * FROM hirf_experiment_images WHERE exp_id = ?",
                    conn, params=(selected_id,)
                )
                conn.close()

                if img_df.empty:
                    st.info("该记录暂无关联图片或数据。")
                else:
                    st.markdown(f"#### 📎 实验附件 ({len(img_df)})")

                    for idx, row in img_df.iterrows():
                        with st.expander(f"附件 {idx + 1}: {row['image_name']}", expanded=True):
                            col_img, col_info = st.columns([2, 1])

                            with col_img:
                                if row['image_data']:
                                    try:
                                        image = Image.open(io.BytesIO(row['image_data']))
                                        st.image(image, use_container_width=True, caption=row['image_name'])
                                    except Exception:
                                        st.error("图片文件损坏")
                                else:
                                    st.write("无图片预览")

                            with col_info:
                                st.markdown("**图片/结果描述:**")
                                st.write(row['image_desc'] or "暂无描述")
                                st.divider()
                                if row['raw_data']:
                                    file_name = row['raw_data_name'] or f"raw_data_{row['img_id']}.dat"
                                    size_kb = len(row['raw_data']) / 1024
                                    st.download_button(
                                        label=f"📥 下载原始数据 ({size_kb:.1f} KB)",
                                        data=row['raw_data'],
                                        file_name=file_name,
                                        mime="application/octet-stream"
                                    )
                                    st.caption(f"文件名: {file_name}")
                                else:
                                    st.caption("🚫 未上传原始数据文件")


def add_hirf_experiment():
    st.subheader("添加HIRF实验记录")

    if 'hirf_add_count' not in st.session_state:
        st.session_state['hirf_add_count'] = 1

    with st.form("add_hirf_form"):
        st.markdown("### 1. 实验基本信息")
        col1, col2, col3 = st.columns(3)
        with col1:
            model = st.text_input("飞机型号 *", placeholder="如: AG600")
            content = st.selectbox("实验内容", ["LLSC", "LLSF"])
        with col2:
            connector_num = st.text_input("连接器编号", placeholder="如: P1201-J1")
            method = st.selectbox("测试方法", ["BCI", "Direct Drive", "Reverberation Chamber", "其他"])
        with col3:
            freq = st.text_input("频率范围", placeholder="如: 10kHz - 400MHz")
            field = st.text_input("场强等级", placeholder="如: 100 V/m")

        desc = st.text_area("实验整体综述", placeholder="描述实验配置、环境、通过判据等...")

        st.markdown("### 2. 结果上传 (图片 + 原始数据)")
        st.info("提示：对于频谱曲线图，建议同时上传对应的 Excel/CSV 原始数据文件，以便后续分析。")

        uploaded_data = []
        for i in range(st.session_state['hirf_add_count']):
            with st.container(border=True):
                st.markdown(f"**附件组 {i + 1}**")

                c_img, c_data = st.columns(2)
                with c_img:
                    f_img = st.file_uploader(f"上传结果图片/截图", type=['jpg', 'png', 'jpeg'], key=f"h_img_{i}")
                with c_data:
                    f_raw = st.file_uploader(f"上传对应的原始数据 (可选)", type=['csv', 'xlsx', 'txt', 'dat', 'mat'],
                                             key=f"h_raw_{i}")

                name = st.text_input("图片标题 *", value=f"测试结果图 {i + 1}", key=f"h_name_{i}")
                d_txt = st.text_area("详细描述", height=68, key=f"h_desc_{i}", placeholder="例如：左副翼内作动器感应电场（均值）")

                uploaded_data.append((f_img, f_raw, name, d_txt))

        col_add, col_remove = st.columns([1, 8])
        with col_add:
            if st.form_submit_button("➕ 增加附件"):
                st.session_state['hirf_add_count'] += 1
                st.rerun()
        with col_remove:
            if st.session_state['hirf_add_count'] > 1 and st.form_submit_button("➖ 减少附件"):
                st.session_state['hirf_add_count'] -= 1
                st.rerun()

        st.markdown("---")
        submitted = st.form_submit_button("提交数据", type="primary")

        if submitted:
            if not model:
                st.error("错误：飞机型号为必填项")
                return

            conn = create_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    '''INSERT INTO hirf_experiments 
                       (aircraft_model, connector_number, experiment_content, test_method, frequency_range, field_strength, description) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (model, connector_num, content, method, freq, field, desc)
                )
                new_id = cursor.lastrowid

                # 插入图片和原始数据
                count = 0
                for f_img, f_raw, f_name, f_desc in uploaded_data:
                    # ✅ 修复: 只要有图片或有数据均允许保存
                    if f_img or f_raw:
                        img_bytes = f_img.read() if f_img else None
                        raw_bytes = f_raw.read() if f_raw else None
                        raw_name = f_raw.name if f_raw else None

                        final_name = f_name if f_name else (f_img.name if f_img else "未命名附件")

                        cursor.execute(
                            '''INSERT INTO hirf_experiment_images 
                               (exp_id, image_name, image_desc, image_data, raw_data, raw_data_name) 
                               VALUES (?, ?, ?, ?, ?, ?)''',
                            (new_id, final_name, f_desc, img_bytes, raw_bytes, raw_name)
                        )
                        count += 1

                conn.commit()
                st.success(f"保存成功！包含 {count} 组数据。")
                st.session_state['hirf_add_count'] = 1
                # ✅ 修复: 提交成功后延迟并强制刷新页面，清空表单残留的脏数据，防止重复提交
                time.sleep(1.0)
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"保存失败: {e}")
            finally:
                conn.close()


def update_hirf_experiment():
    st.subheader("修改HIRF实验数据")

    conn = create_connection()
    try:
        df = pd.read_sql_query(
            "SELECT id, aircraft_model, connector_number, experiment_content, test_method, frequency_range FROM hirf_experiments ORDER BY id DESC",
            conn)
    except:
        df = pd.read_sql_query("SELECT * FROM hirf_experiments ORDER BY id DESC", conn)

    if df.empty:
        st.warning("无数据可修改。")
        conn.close()
        return

    selected_id = st.selectbox("选择记录:", df['id'],
                               format_func=lambda
                                   x: f"ID:{x} - {df[df['id'] == x]['aircraft_model'].iloc[0]} (Conn: {df[df['id'] == x].get('connector_number', pd.Series(['N/A'])).iloc[0]})")

    # 获取当前详情
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hirf_experiments WHERE id=?", (selected_id,))
    rec_dict = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))

    # 获取当前图片
    img_df = pd.read_sql_query("SELECT * FROM hirf_experiment_images WHERE exp_id=?", conn, params=(selected_id,))

    # ✅ 修复: 页面渲染前尽早关闭数据库查询连接，防止 Streamlit 组件交互导致连接泄露
    conn.close()

    if 'hirf_up_add_count' not in st.session_state:
        st.session_state['hirf_up_add_count'] = 0

    with st.form("update_form"):
        c1, c2, c3 = st.columns(3)
        new_model = c1.text_input("飞机型号", value=rec_dict.get('aircraft_model'))
        new_connector = c1.text_input("连接器编号", value=rec_dict.get('connector_number', ''))

        curr_content = rec_dict.get('experiment_content')
        content_opts = ["LLSC", "LLSF"]
        c_idx = content_opts.index(curr_content) if curr_content in content_opts else 0
        new_content = c2.selectbox("实验内容", content_opts, index=c_idx)

        curr_method = rec_dict.get('test_method')
        method_opts = ["BCI", "Direct Drive", "Reverberation Chamber", "其他"]
        m_idx = method_opts.index(curr_method) if curr_method in method_opts else 0
        new_method = c2.selectbox("测试方法", method_opts, index=m_idx)

        new_freq = c3.text_input("频率范围", value=rec_dict.get('frequency_range'))
        new_field = c3.text_input("场强等级", value=rec_dict.get('field_strength'))

        new_desc = st.text_area("实验综述", value=rec_dict.get('description'))

        st.markdown("### 现有附件管理")
        existing_ops = {}

        if not img_df.empty:
            for idx, row in img_df.iterrows():
                iid = row['img_id']
                with st.expander(f"编辑附件: {row['image_name']}", expanded=False):
                    col_del, col_edit = st.columns([1, 4])
                    with col_del:
                        st.write(" ")
                        st.write(" ")
                        delete_flag = st.checkbox("🗑️ 删除", key=f"ud_{iid}")
                    with col_edit:
                        u_name = st.text_input("标题", value=row['image_name'], key=f"un_{iid}")
                        u_desc = st.text_area("描述", value=row['image_desc'], key=f"udsc_{iid}")

                        if row['raw_data']:
                            st.caption(f"✅ 已包含原始数据: {row['raw_data_name']}")
                        else:
                            st.caption("❌ 无原始数据")

                        u_raw = st.file_uploader("覆盖/上传原始数据", key=f"ur_{iid}")

                    existing_ops[iid] = {
                        "delete": delete_flag,
                        "name": u_name,
                        "desc": u_desc,
                        "new_raw": u_raw
                    }

        st.markdown("### 新增附件")
        new_uploads = []
        for i in range(st.session_state['hirf_up_add_count']):
            st.caption(f"新增附件 {i + 1}")
            nf_img = st.file_uploader(f"图片 {i + 1}", key=f"n_img_{i}")
            nf_raw = st.file_uploader(f"数据 {i + 1}", key=f"n_raw_{i}")
            nf_name = st.text_input(f"标题 {i + 1}", key=f"n_name_{i}")
            nf_desc = st.text_area(f"描述 {i + 1}", key=f"n_desc_{i}")
            new_uploads.append((nf_img, nf_raw, nf_name, nf_desc))
            st.divider()

        ca, cr = st.columns([1, 8])
        with ca:
            if st.form_submit_button("➕"):
                st.session_state['hirf_up_add_count'] += 1
                st.rerun()
        with cr:
            if st.session_state['hirf_up_add_count'] > 0 and st.form_submit_button("➖"):
                st.session_state['hirf_up_add_count'] -= 1
                st.rerun()

        if st.form_submit_button("确认更新", type="primary"):
            # ✅ 修复: 在确认更新事件触发时，才重新创建数据库连接进行写入
            write_conn = create_connection()
            write_cursor = write_conn.cursor()
            try:
                write_cursor.execute('''
                    UPDATE hirf_experiments 
                    SET aircraft_model=?, connector_number=?, experiment_content=?, test_method=?, frequency_range=?, field_strength=?, description=?
                    WHERE id=?
                ''', (new_model, new_connector, new_content, new_method, new_freq, new_field, new_desc, selected_id))

                for iid, ops in existing_ops.items():
                    if ops['delete']:
                        write_cursor.execute("DELETE FROM hirf_experiment_images WHERE img_id=?", (iid,))
                    else:
                        if ops['new_raw']:
                            r_bytes = ops['new_raw'].read()
                            r_name = ops['new_raw'].name
                            write_cursor.execute(
                                "UPDATE hirf_experiment_images SET image_name=?, image_desc=?, raw_data=?, raw_data_name=? WHERE img_id=?",
                                (ops['name'], ops['desc'], r_bytes, r_name, iid)
                            )
                        else:
                            write_cursor.execute(
                                "UPDATE hirf_experiment_images SET image_name=?, image_desc=? WHERE img_id=?",
                                (ops['name'], ops['desc'], iid)
                            )

                for nf_img, nf_raw, nf_name, nf_desc in new_uploads:
                    # ✅ 修复: 只要有图片或有数据均允许保存
                    if nf_img or nf_raw:
                        ib = nf_img.read() if nf_img else None
                        rb = nf_raw.read() if nf_raw else None
                        rn = nf_raw.name if nf_raw else None
                        final_n = nf_name if nf_name else (nf_img.name if nf_img else "未命名附件")

                        write_cursor.execute(
                            '''INSERT INTO hirf_experiment_images 
                               (exp_id, image_name, image_desc, image_data, raw_data, raw_data_name) 
                               VALUES (?, ?, ?, ?, ?, ?)''',
                            (selected_id, final_n, nf_desc, ib, rb, rn)
                        )

                write_conn.commit()
                st.success("更新成功")
                st.session_state['hirf_up_add_count'] = 0
                time.sleep(1.0)
                st.rerun()
            except Exception as e:
                write_conn.rollback()
                st.error(f"更新失败: {e}")
            finally:
                write_conn.close()


def delete_hirf_experiment():
    st.subheader("删除HIRF实验记录")

    # --- 搜索栏 ---
    with st.container(border=True):
        st.markdown("**1. 检索需要删除的记录**")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            search_model = st.text_input("飞机型号 (删除检索)", placeholder="如: AG600")
        with col2:
            search_connector = st.text_input("连接器编号 (删除检索)", placeholder="如: J1201")
        with col3:
            search_content = st.selectbox("实验内容 (删除检索)", ["所有", "LLSC", "LLSF"], index=0)
        with col4:
            search_method = st.selectbox("测试方法 (删除检索)", ["所有", "BCI", "Direct Drive", "其他"], index=0)
        with col5:
            search_freq = st.text_input("频段 (删除检索)", placeholder="如: 100MHz")

    if 'hirf_delete_search_result' not in st.session_state:
        st.session_state['hirf_delete_search_result'] = None

    if st.button("查询以删除"):
        conn = create_connection()
        query = "SELECT id, aircraft_model, connector_number, experiment_content, test_method, frequency_range, field_strength, upload_date FROM hirf_experiments WHERE 1=1"
        params = []

        if search_model:
            query += " AND aircraft_model LIKE ?"
            params.append(f"%{search_model}%")
        if search_connector:
            query += " AND connector_number LIKE ?"
            params.append(f"%{search_connector}%")
        if search_content and search_content != "所有":
            query += " AND experiment_content = ?"
            params.append(search_content)
        if search_method and search_method != "所有":
            query += " AND test_method = ?"
            params.append(search_method)
        if search_freq:
            query += " AND frequency_range LIKE ?"
            params.append(f"%{search_freq}%")

        query += " ORDER BY upload_date DESC"

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        st.session_state['hirf_delete_search_result'] = df

    # --- 结果展示与批量删除 ---
    if st.session_state['hirf_delete_search_result'] is not None:
        df = st.session_state['hirf_delete_search_result']

        if df.empty:
            st.warning("没有找到匹配的记录。")
        else:
            st.markdown("---")
            st.markdown("**2. 在下方表格第一列勾选需要删除的记录**")

            df_to_edit = df.copy()
            df_to_edit.insert(0, '选择删除', False)

            edited_df = st.data_editor(
                df_to_edit,
                column_config={
                    "选择删除": st.column_config.CheckboxColumn(
                        "🗑️ 勾选删除",
                        help="勾选需要彻底删除的记录",
                        default=False,
                    )
                },
                disabled=['id', 'aircraft_model', 'connector_number', 'experiment_content', 'test_method',
                          'frequency_range', 'field_strength', 'upload_date'],
                hide_index=True,
                use_container_width=True,
                key="delete_data_editor"
            )

            selected_rows = edited_df[edited_df['选择删除'] == True]

            if not selected_rows.empty:
                st.warning(f"⚠️ 警告: 已勾选 **{len(selected_rows)}** 条记录。删除后相关图片和原始数据也会被一并清除，此操作不可恢复！")
                if st.button("确认删除选中记录", type="primary"):
                    conn = create_connection()
                    cursor = conn.cursor()
                    try:
                        ids_to_delete = selected_rows['id'].tolist()
                        placeholders = ','.join(['?'] * len(ids_to_delete))
                        delete_sql = f"DELETE FROM hirf_experiments WHERE id IN ({placeholders})"

                        cursor.execute(delete_sql, ids_to_delete)
                        conn.commit()

                        st.success(f"成功删除 {len(ids_to_delete)} 条记录！")
                        st.session_state['hirf_delete_search_result'] = None
                        time.sleep(1.0)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"删除失败: {e}")
                    finally:
                        conn.close()


# 关于页面
def about_page():
    st.header("关于")
    st.write("""
    ### 飞机HIRF环境实验数据库 v2.3

    **本次更新:**
    - **修复附件上传Bug**: 支持仅上传原始数据(不强制上传图片)。
    - **修复重复提交Bug**: 数据提交/更新完成后强行清空表单残留数据。
    - **修复数据库连接泄露**: 优化修改页面的SQLite连接资源管理。
    - **新增批量删除**: 在“删除数据”页面支持条件检索及表格可视化批量勾选删除。

    **功能特性:**
    - 支持 LLSC, LLSF 实验内容分类。
    - 支持 BCI, Direct Drive 等不同测试方法的分类。
    - 支持上传与图片对应的 **原始数据文件 (Excel/CSV/DAT)**。
    - 数据库自动迁移，无需手动更改表结构。
    """)


# ================= 3. 主页面入口 =================

def main():
    LOGO_PATH = "company_logo.jpg"
    if not os.path.exists(LOGO_PATH):
        try:
            pass
        except:
            pass
    logo_base64 = wyz_io.image_to_base64(LOGO_PATH)

    if logo_base64:
        logo_html = f"""
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
            <img src="data:image/jpeg;base64,{logo_base64}" alt="公司标徽" style="height: 60px;">
            <h3 style="margin: 0; font-size: 42px;">中航通飞华南飞机工业有限公司</h3>
        </div>
        """
        st.markdown(logo_html, unsafe_allow_html=True)
    else:
        st.header("中航通飞华南飞机工业有限公司")

    st.title("飞机HIRF环境实验数据库")

    operation = st.sidebar.radio("选择操作", ["查看数据", "添加数据", "修改数据", "删除数据", "关于"])

    if operation == "查看数据":
        view_hirf_experiments()
    elif operation == "添加数据":
        add_hirf_experiment()
    elif operation == "修改数据":
        update_hirf_experiment()
    elif operation == "删除数据":
        delete_hirf_experiment()
    else:
        about_page()


# if __name__ == "__main__":
main()