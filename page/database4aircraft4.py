import streamlit as st
import sqlite3
import os
import pandas as pd
from PIL import Image
import io

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
        test_method TEXT,      -- 新增: 测试方法 (如 LLSF, BCI, Direct Drive)
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
        print("已添加字段: test_method")

    # 2. HIRF 实验图片/数据表
    # 注意：我们将 raw_data 放在这里，因为往往一张图对应一份特定的测试数据
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hirf_experiment_images (
        img_id INTEGER PRIMARY KEY AUTOINCREMENT,
        exp_id INTEGER,
        image_name TEXT,
        image_desc TEXT,
        image_data BLOB,
        raw_data BLOB,         -- 新增: 用于存储生成该图片的原始数据文件(.csv/.xlsx/.dat)
        raw_data_name TEXT,    -- 新增: 原始文件名
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
        print("已添加字段: raw_data, raw_data_name")

    conn.commit()
    conn.close()


# 初始化数据库
init_db()


# ================= 2. 功能模块实现 =================

def view_hirf_experiments():
    st.subheader("查看HIRF实验数据")

    # --- 搜索栏 ---
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            search_model = st.text_input("飞机型号", placeholder="如: AG600")
        with col2:
            search_method = st.selectbox("测试方法", ["所有", "LLSF", "BCI", "Direct Drive", "其他"], index=0)
        with col3:
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
                df[['id', 'aircraft_model', 'test_method', 'frequency_range', 'field_strength', 'upload_date']],
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.subheader("📊 详细视图与图谱")

            # 选择记录
            selected_id = st.selectbox(
                "选择记录查看详情:",
                df['id'],
                format_func=lambda
                    x: f"ID:{x} | {df[df['id'] == x]['aircraft_model'].iloc[0]} - {df[df['id'] == x]['test_method'].iloc[0] or '未分类'}"
            )

            if selected_id:
                record = df[df['id'] == selected_id].iloc[0]

                # 1. 基础信息卡片
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.markdown(f"**飞机型号:**\n{record['aircraft_model']}")
                    c2.markdown(f"**测试方法:**\n{record['test_method'] or '未填写'}")
                    c3.markdown(f"**频率范围:**\n{record['frequency_range']}")
                    c4.markdown(f"**场强等级:**\n{record['field_strength']}")

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
                        # 使用 expander 包裹每张图，方便收起/展开，且默认可以看大图
                        with st.expander(f"附件 {idx + 1}: {row['image_name']}", expanded=True):

                            col_img, col_info = st.columns([2, 1])  # 图片占 2/3 宽度，保证曲线清晰

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
                                # 下载原始数据按钮
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
        col1, col2 = st.columns(2)
        with col1:
            model = st.text_input("飞机型号 *", placeholder="如: AG600")
            # 增加测试方法选择，适配你的 LLSF 图片
            method = st.selectbox("测试方法", ["LLSF", "BCI", "Direct Drive", "Reverberation Chamber", "其他"])
        with col2:
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

        # 动态增删按钮
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
                # 插入主表
                cursor.execute(
                    '''INSERT INTO hirf_experiments 
                       (aircraft_model, test_method, frequency_range, field_strength, description) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (model, method, freq, field, desc)
                )
                new_id = cursor.lastrowid

                # 插入图片和原始数据
                count = 0
                for f_img, f_raw, f_name, f_desc in uploaded_data:
                    if f_img:
                        img_bytes = f_img.read()
                        # 处理原始数据
                        raw_bytes = None
                        raw_name = None
                        if f_raw:
                            raw_bytes = f_raw.read()
                            raw_name = f_raw.name

                        final_name = f_name if f_name else f_img.name

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

            except Exception as e:
                conn.rollback()
                st.error(f"保存失败: {e}")
            finally:
                conn.close()


def update_hirf_experiment():
    st.subheader("修改HIRF实验数据")

    conn = create_connection()
    # 兼容旧数据的查询（如果没有 test_method 字段可能会报错，但 init_db 已处理）
    try:
        df = pd.read_sql_query(
            "SELECT id, aircraft_model, test_method, frequency_range FROM hirf_experiments ORDER BY id DESC", conn)
    except:
        df = pd.read_sql_query("SELECT id, aircraft_model, frequency_range FROM hirf_experiments ORDER BY id DESC",
                               conn)

    if df.empty:
        st.warning("无数据可修改。")
        conn.close()
        return

    selected_id = st.selectbox("选择记录:", df['id'],
                               format_func=lambda x: f"ID:{x} - {df[df['id'] == x]['aircraft_model'].iloc[0]}")

    # 获取当前详情
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hirf_experiments WHERE id=?", (selected_id,))
    rec_dict = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))

    # 获取当前图片
    img_df = pd.read_sql_query("SELECT * FROM hirf_experiment_images WHERE exp_id=?", conn, params=(selected_id,))

    # Session用于新增
    if 'hirf_up_add_count' not in st.session_state:
        st.session_state['hirf_up_add_count'] = 0

    with st.form("update_form"):
        c1, c2 = st.columns(2)
        new_model = c1.text_input("飞机型号", value=rec_dict.get('aircraft_model'))

        # 处理 test_method 回显
        curr_method = rec_dict.get('test_method')
        method_opts = ["LLSF", "BCI", "Direct Drive", "Reverberation Chamber", "其他"]
        m_idx = method_opts.index(curr_method) if curr_method in method_opts else 0
        new_method = c2.selectbox("测试方法", method_opts, index=m_idx)

        c3, c4 = st.columns(2)
        new_freq = c3.text_input("频率范围", value=rec_dict.get('frequency_range'))
        new_field = c4.text_input("场强等级", value=rec_dict.get('field_strength'))

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

                        # 显示当前是否有原始数据
                        if row['raw_data']:
                            st.caption(f"✅ 已包含原始数据: {row['raw_data_name']}")
                        else:
                            st.caption("❌ 无原始数据")

                        # 允许覆盖上传原始数据
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

        # 动态按钮
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
            try:
                # 更新主表
                cursor.execute('''
                    UPDATE hirf_experiments 
                    SET aircraft_model=?, test_method=?, frequency_range=?, field_strength=?, description=?
                    WHERE id=?
                ''', (new_model, new_method, new_freq, new_field, new_desc, selected_id))

                # 更新现有附件
                for iid, ops in existing_ops.items():
                    if ops['delete']:
                        cursor.execute("DELETE FROM hirf_experiment_images WHERE img_id=?", (iid,))
                    else:
                        # 如果上传了新数据文件，则更新数据文件，否则只更新文本
                        if ops['new_raw']:
                            r_bytes = ops['new_raw'].read()
                            r_name = ops['new_raw'].name
                            cursor.execute(
                                "UPDATE hirf_experiment_images SET image_name=?, image_desc=?, raw_data=?, raw_data_name=? WHERE img_id=?",
                                (ops['name'], ops['desc'], r_bytes, r_name, iid)
                            )
                        else:
                            cursor.execute(
                                "UPDATE hirf_experiment_images SET image_name=?, image_desc=? WHERE img_id=?",
                                (ops['name'], ops['desc'], iid)
                            )

                # 插入新附件
                for nf_img, nf_raw, nf_name, nf_desc in new_uploads:
                    if nf_img:
                        ib = nf_img.read()
                        rb = nf_raw.read() if nf_raw else None
                        rn = nf_raw.name if nf_raw else None
                        final_n = nf_name if nf_name else nf_img.name

                        cursor.execute(
                            '''INSERT INTO hirf_experiment_images 
                               (exp_id, image_name, image_desc, image_data, raw_data, raw_data_name) 
                               VALUES (?, ?, ?, ?, ?, ?)''',
                            (selected_id, final_n, nf_desc, ib, rb, rn)
                        )

                conn.commit()
                st.success("更新成功")
                st.session_state['hirf_up_add_count'] = 0
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"更新失败: {e}")
            finally:
                conn.close()


def delete_hirf_experiment():
    st.subheader("删除HIRF实验记录")
    conn = create_connection()
    df = pd.read_sql_query("SELECT id, aircraft_model FROM hirf_experiments", conn)

    if df.empty:
        st.warning("无数据。")
        conn.close()
        return

    selected_id = st.selectbox("选择记录:", df['id'],
                               format_func=lambda x: f"ID:{x} - {df[df['id'] == x]['aircraft_model'].iloc[0]}")

    if st.button("确认删除"):
        try:
            conn.execute("DELETE FROM hirf_experiments WHERE id=?", (selected_id,))
            conn.commit()
            st.success("删除成功")
            st.rerun()
        except Exception as e:
            st.error(f"删除失败: {e}")
        finally:
            conn.close()


# 关于页面
def about_page():
    st.header("关于")
    st.write("""
    ### 飞机HIRF环境实验数据库 v2.0

    **针对图片类型优化:**
    - 支持 LLSF, BCI 等不同测试方法的分类。
    - 支持上传与图片对应的 **原始数据文件 (Excel/CSV/DAT)**，解决“有图无数据”的痛点。
    - 优化了详细曲线图的显示布局，便于观察坐标轴数值。
    """)


# ================= 3. 主页面入口 =================

def main():
    # Logo 逻辑
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


#if __name__ == "__main__":
main()