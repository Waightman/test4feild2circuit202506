import streamlit as st
import sqlite3
import os
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import io
import re
import zipfile  # <--- 新增
import numpy as np  # <--- 新增
# 设置 Matplotlib 中文字体 (防止中文乱码)
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# 模拟 wyz_io 模块，用于本地测试
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


# 创建或连接数据库
def create_connection():
    conn = sqlite3.connect('aircraft_lightning.db')
    return conn


# 初始化数据库表 (包含结构更新逻辑)
def init_db():
    conn = create_connection()
    cursor = conn.cursor()

    # 1. 创建雷电分区主表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS lightning_zones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aircraft_model TEXT NOT NULL UNIQUE,
        description TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. 创建雷电分区图片表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS lightning_zone_images (
        img_id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_id INTEGER,
        image_name TEXT,
        image_data BLOB,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (zone_id) REFERENCES lightning_zones (id) ON DELETE CASCADE
    )
    ''')

    # 3. 创建雷电间击环境表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS indirect_effects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aircraft_model TEXT NOT NULL,
        test_point TEXT NOT NULL,
        current_in_out TEXT,
        voltage_probe_point TEXT,
        waveform_type TEXT,  -- 现作为"激励波形"
        test_object_type TEXT CHECK(test_object_type IN ('线束', '针脚')),
        data_file BLOB,
        data_type TEXT CHECK(data_type IN ('voltage', 'current')),
        data_unit TEXT,
        description TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 4. 创建雷电间击环境excel表
    cursor.execute('''
CREATE TABLE IF NOT EXISTS aircraft_excel_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aircraft_model TEXT NOT NULL,
    filename TEXT,
    excel_data BLOB, -- 存储整个文件
    description TEXT,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # --- 数据库结构迁移：检查并添加新字段 ---
    # 尝试添加 data_domain (数据域) 字段
    try:
        cursor.execute("SELECT data_domain FROM indirect_effects LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE indirect_effects ADD COLUMN data_domain TEXT")
        print("已添加字段: data_domain")

    # 尝试添加 induced_waveform (感应波形) 字段
    try:
        cursor.execute("SELECT induced_waveform FROM indirect_effects LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE indirect_effects ADD COLUMN induced_waveform TEXT")
        print("已添加字段: induced_waveform")
    # ------------------------------------

    conn.commit()
    conn.close()


# 初始化数据库
init_db()


# 主页面
def main():
    #fix_database_structure()
    #########0  显示公司logo
    LOGO_PATH = "company_logo.jpg"
    if not os.path.exists(LOGO_PATH):
        try:
            # 仅作演示，实际环境请确保图片存在
            pass
        except Exception:
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

    st.title("飞机雷电分区/雷电间击环境数据库")

    # 侧边栏导航
    menu = ["雷电分区数据库", "雷电间击环境数据库", "关于"]
    choice = st.sidebar.selectbox("子数据库选择", menu)
    # 操作选项
    operation = st.sidebar.radio("选择操作", ["查看数据", "添加数据", "修改数据", "删除数据"])

    if choice == "雷电分区数据库":
        lightning_zones_page(operation)
    elif choice == "雷电间击环境数据库":
        indirect_effects_page(operation)
    else:
        about_page()


# ... (雷电分区数据库相关函数 lightning_zones_page, view_lightning_zones, add_lightning_zone, update_lightning_zone, delete_lightning_zone 保持不变，此处省略以节省篇幅，请保留原代码) ...
# 为了代码完整性，这里简单的把雷电分区的入口函数保留，具体实现复用你原有的即可
def lightning_zones_page(operation):
    # 这里请保留你原有的 lightning_zones_page 及相关子函数的实现
    # 仅为了演示修改后的间击环境部分，这里暂时放个占位符，实际使用请粘贴原有代码
    st.header("雷电分区数据库")
    if operation == "查看数据":
        view_lightning_zones()  # 请确保此函数在你代码中定义
    elif operation == "添加数据":
        add_lightning_zone()  # 请确保此函数在你代码中定义
    elif operation == "修改数据":
        update_lightning_zone()  # 请确保此函数在你代码中定义
    elif operation == "删除数据":
        delete_lightning_zone()  # 请确保此函数在你代码中定义


# (以下是需要插入/保留的雷电分区辅助函数，请直接使用你原本的代码，这里不重复打印以突出修改点)
# ... [保留 view_lightning_zones, add_lightning_zone, update_lightning_zone, delete_lightning_zone 代码] ...
# 假设上方代码未变，下面重点修改 雷电间击环境数据库 部分
# ========== 雷电分区数据库功能 ==========
def view_lightning_zones():
    st.subheader("查看雷电分区数据")
    # 搜索选项
    aircraft_model = st.text_input("输入飞机型号进行搜索", "")

    # --- 修改开始：使用 session_state ---

    # 初始化 session_state 中的变量，防止报错
    if 'lz_search_result' not in st.session_state:
        st.session_state['lz_search_result'] = None

    # 点击查询按钮时，执行查询并将结果存入 session_state
    if st.button("查询"):
        conn = create_connection()
        if aircraft_model:
            query = "SELECT id, aircraft_model, description, upload_date FROM lightning_zones WHERE aircraft_model LIKE ?"
            params = (f"%{aircraft_model}%",)
        else:
            query = "SELECT id, aircraft_model, description, upload_date FROM lightning_zones"
            params = ()

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        # 将结果保存到状态中
        st.session_state['lz_search_result'] = df

    # --- 显示逻辑：判断 session_state 中是否有数据 ---

    if st.session_state['lz_search_result'] is not None:
        df = st.session_state['lz_search_result']

        if df.empty:
            st.warning("没有找到匹配的记录")
        else:
            st.dataframe(df)

            # 显示选中的图片
            # 注意：selectbox 也会触发重运行，但因为 df 存在 session_state 里，所以下一次运行能进到这里
            selected_id = st.selectbox("选择记录查看详细信息", df['id'],
                                       format_func=lambda x: f"ID: {x} - {df[df['id'] == x]['aircraft_model'].iloc[0]}")

            selected_record = df[df['id'] == selected_id].iloc[0]
            st.markdown(f"**飞机型号:** {selected_record['aircraft_model']}")
            st.write(f"**描述:** {selected_record['description'] or '无'}")
            st.write(f"**上传日期:** {selected_record['upload_date']}")
            st.markdown("---")
            st.subheader("关联视图")

            conn = create_connection()  # 重新连接以获取图片细节
            # 查询关联图片
            image_query = "SELECT image_name, image_data FROM lightning_zone_images WHERE zone_id = ?"
            image_df = pd.read_sql_query(image_query, conn, params=(selected_id,))
            conn.close()

            if image_df.empty:
                st.info("该记录没有上传视图。")
            else:
                for index, row in image_df.iterrows():
                    image_data = row['image_data']
                    image_name = row['image_name']

                    st.markdown(f"**{image_name}**")
                    if image_data is not None:
                        try:
                            image = Image.open(io.BytesIO(image_data))
                            st.image(image, caption=image_name)
                        except Exception as e:
                            st.error(f"无法显示视图 '{image_name}': {e}")
                    else:
                        st.warning(f"视图 '{image_name}' 没有图片数据")
                    st.markdown("---")
    else:
        st.info("请输入搜索条件并点击查询按钮")


def add_lightning_zone():
    st.subheader("添加雷电分区数据 (支持多视图)")

    if 'image_count' not in st.session_state:
        st.session_state['image_count'] = 1

    with st.form("add_lightning_zone_form"):
        aircraft_model = st.text_input("飞机型号*", "")
        description = st.text_area("整体描述", "")

        st.markdown("### 视图上传")

        uploaded_files = []
        for i in range(st.session_state['image_count']):
            col1, col2 = st.columns([1, 2])
            with col1:
                # 使用唯一的 key
                file = st.file_uploader(f"视图 {i + 1} 图片", type=["jpg", "jpeg", "png"], key=f"file_uploader_{i}")
            with col2:
                # 使用唯一的 key
                name = st.text_input(f"视图 {i + 1} 名称/描述*", key=f"image_name_{i}")
            uploaded_files.append((file, name))
            st.markdown("---")

        col_add, col_remove = st.columns([1, 10])
        with col_add:
            if st.form_submit_button("➕"):
                st.session_state['image_count'] += 1
                st.rerun()  # 重新运行以显示新的文件上传框
        with col_remove:
            if st.session_state['image_count'] > 1 and st.form_submit_button("➖"):
                st.session_state['image_count'] -= 1
                st.rerun()  # 重新运行以移除文件上传框

        submitted = st.form_submit_button("提交数据")

        if submitted:
            if not aircraft_model:
                st.error("飞机型号是必填项")
                return

            conn = create_connection()
            cursor = conn.cursor()

            try:
                # 1. 插入主记录
                cursor.execute(
                    "INSERT INTO lightning_zones (aircraft_model, description) VALUES (?, ?)",
                    (aircraft_model, description)
                )
                zone_id = cursor.lastrowid

                # 2. 插入图片记录
                for file, name in uploaded_files:
                    if file and name:
                        image_bytes = file.read()
                        cursor.execute(
                            "INSERT INTO lightning_zone_images (zone_id, image_name, image_data) VALUES (?, ?, ?)",
                            (zone_id, name, image_bytes)
                        )
                    elif file and not name:
                        st.warning(f"图片 '{file.name}' 已上传，但未提供描述。")
                        image_bytes = file.read()
                        cursor.execute(
                            "INSERT INTO lightning_zone_images (zone_id, image_name, image_data) VALUES (?, ?, ?)",
                            (zone_id, file.name, image_bytes)
                        )
                    elif name and not file:
                        st.warning(f"视图名称/描述 '{name}' 已填写，但未上传图片文件。将只存储描述。")
                        cursor.execute(
                            "INSERT INTO lightning_zone_images (zone_id, image_name, image_data) VALUES (?, ?, ?)",
                            (zone_id, name, None)
                        )

                conn.commit()
                st.success(f"飞机型号 '{aircraft_model}' 数据及 {len([f for f, n in uploaded_files if f or n])} 个视图信息添加成功!")
                # 重置计数器
                st.session_state['image_count'] = 1
            except sqlite3.IntegrityError:
                st.error(f"添加数据时出错: 飞机型号 '{aircraft_model}' 已存在，请选择修改数据操作或更换型号。")
            except Exception as e:
                conn.rollback()
                st.error(f"添加数据时出错: {e}")
            finally:
                conn.close()


def update_lightning_zone():
    st.subheader("修改雷电分区数据 (支持多视图)")

    conn = create_connection()
    df = pd.read_sql_query("SELECT id, aircraft_model FROM lightning_zones", conn)

    if df.empty:
        st.warning("数据库中没有记录可供修改")
        conn.close()
        return

    selected_id = st.selectbox("选择要修改的记录", df['id'],
                               format_func=lambda x: f"ID: {x} - {df[df['id'] == x]['aircraft_model'].iloc[0]}")

    cursor = conn.cursor()
    cursor.execute("SELECT id, aircraft_model, description FROM lightning_zones WHERE id = ?", (selected_id,))
    record = cursor.fetchone()

    if not record:
        st.error("未找到选定的记录")
        conn.close()
        return

    # 查询现有图片
    current_images_df = pd.read_sql_query(
        "SELECT img_id, image_name, image_data FROM lightning_zone_images WHERE zone_id = ?",
        conn, params=(selected_id,)
    )

    if 'new_image_count' not in st.session_state:
        st.session_state['new_image_count'] = 0

    with st.form("update_lightning_zone_form"):
        aircraft_model = st.text_input("飞机型号*", record[1])
        description = st.text_area("整体描述", record[2] or "")

        st.markdown("### 修改现有视图")

        updated_images_data = {}  # 存储现有图片的修改

        if current_images_df.empty:
            st.info("该记录没有关联视图。")
        else:
            for index, row in current_images_df.iterrows():
                img_id = row['img_id']
                image_data = row['image_data']

                st.markdown(f"**视图 ID: {img_id}**")

                col1, col2 = st.columns([1, 2])
                with col1:
                    # 显示当前图片
                    if image_data is not None:
                        try:
                            image = Image.open(io.BytesIO(image_data))
                            st.image(image, caption="当前视图")
                        except:
                            st.error("无法显示当前视图")
                    else:
                        st.write("当前无图片文件")

                    # 上传新图片替换
                    new_file = st.file_uploader(f"替换图片 (ID:{img_id})", type=["jpg", "jpeg", "png"],
                                                key=f"update_file_{img_id}")

                    # 删除选项
                    delete_flag = st.checkbox(f"删除此视图 (ID:{img_id})", key=f"delete_img_{img_id}")

                with col2:
                    # 修改图片描述
                    new_name = st.text_input(f"新名称/描述 (ID:{img_id})", row['image_name'] or "",
                                             key=f"update_name_{img_id}")

                # 记录修改
                updated_images_data[img_id] = {
                    'name': new_name,
                    'file': new_file,
                    'delete': delete_flag
                }
                st.markdown("---")

        st.markdown("### 增加新视图")

        new_uploaded_files = []
        for i in range(st.session_state['new_image_count']):
            col1, col2 = st.columns([1, 2])
            with col1:
                # 使用唯一的 key
                file = st.file_uploader(f"新增视图 {i + 1} 图片", type=["jpg", "jpeg", "png"], key=f"new_file_uploader_{i}")
            with col2:
                # 使用唯一的 key
                name = st.text_input(f"新增视图 {i + 1} 名称/描述*", key=f"new_image_name_{i}")
            new_uploaded_files.append((file, name))
            st.markdown("---")

        col_add, col_remove = st.columns([1, 10])
        with col_add:
            if st.form_submit_button("➕ 增加新视图"):
                st.session_state['new_image_count'] += 1
                st.rerun()
        with col_remove:
            if st.session_state['new_image_count'] > 0 and st.form_submit_button("➖ 移除上一个新增视图"):
                st.session_state['new_image_count'] -= 1
                st.rerun()

        submitted = st.form_submit_button("更新数据")

        if submitted:
            if not aircraft_model:
                st.error("飞机型号是必填项")
                conn.close()
                return

            try:
                # 1. 更新主记录
                cursor.execute(
                    "UPDATE lightning_zones SET aircraft_model = ?, description = ? WHERE id = ?",
                    (aircraft_model, description, selected_id)
                )

                # 2. 处理现有图片修改
                for img_id, data in updated_images_data.items():
                    if data['delete']:
                        # 删除图片
                        cursor.execute("DELETE FROM lightning_zone_images WHERE img_id = ?", (img_id,))
                        st.success(f"视图 ID:{img_id} 已删除。")
                        continue

                    new_image_bytes = None
                    if data['file'] is not None:
                        new_image_bytes = data['file'].read()

                    # 获取原始图片数据，如果新文件为空，则保持不变
                    original_image_data = current_images_df[current_images_df['img_id'] == img_id]['image_data'].iloc[0]

                    image_to_save = new_image_bytes if new_image_bytes is not None else original_image_data

                    # 更新图片和描述
                    cursor.execute(
                        "UPDATE lightning_zone_images SET image_name = ?, image_data = ? WHERE img_id = ?",
                        (data['name'], image_to_save, img_id)
                    )

                # 3. 处理新增图片
                new_count = 0
                for file, name in new_uploaded_files:
                    if file and name:
                        image_bytes = file.read()
                        cursor.execute(
                            "INSERT INTO lightning_zone_images (zone_id, image_name, image_data) VALUES (?, ?, ?)",
                            (selected_id, name, image_bytes)
                        )
                        new_count += 1
                    elif file and not name:
                        st.warning(f"新增图片 '{file.name}' 已上传，但未提供描述。已使用文件名。")
                        image_bytes = file.read()
                        cursor.execute(
                            "INSERT INTO lightning_zone_images (zone_id, image_name, image_data) VALUES (?, ?, ?)",
                            (selected_id, file.name, image_bytes)
                        )
                        new_count += 1
                    elif name and not file:
                        st.warning(f"新增视图名称/描述 '{name}' 已填写，但未上传图片文件。已存储描述。")
                        cursor.execute(
                            "INSERT INTO lightning_zone_images (zone_id, image_name, image_data) VALUES (?, ?, ?)",
                            (selected_id, name, None)
                        )
                        new_count += 1

                conn.commit()
                st.success(f"数据更新成功! (新增 {new_count} 个视图)")
                # 重置新增计数器
                st.session_state['new_image_count'] = 0
                st.rerun()  # 刷新以显示最新数据
            except Exception as e:
                conn.rollback()
                st.error(f"更新数据时出错: {e}")
            finally:
                conn.close()


def delete_lightning_zone():
    st.subheader("删除雷电分区数据")

    conn = create_connection()
    df = pd.read_sql_query("SELECT id, aircraft_model FROM lightning_zones", conn)

    if df.empty:
        st.warning("数据库中没有记录可供删除")
        conn.close()
        return

    selected_id = st.selectbox("选择要删除的记录", df['id'],
                               format_func=lambda x: f"ID: {x} - {df[df['id'] == x]['aircraft_model'].iloc[0]}")

    cursor = conn.cursor()
    cursor.execute("SELECT aircraft_model FROM lightning_zones WHERE id = ?", (selected_id,))
    record = cursor.fetchone()

    if not record:
        st.error("未找到选定的记录")
        conn.close()
        return

    st.warning(f"您确定要删除飞机型号为 '{record[0]}' 的记录吗? **这将同时删除所有关联视图!**")

    if st.button("确认删除"):
        try:
            # 由于 lightning_zone_images 表设置了 ON DELETE CASCADE，只需删除主记录
            cursor.execute("DELETE FROM lightning_zones WHERE id = ?", (selected_id,))
            conn.commit()
            st.success("记录及其所有关联视图删除成功!")
            st.rerun()  # 刷新选择框
        except Exception as e:
            st.error(f"删除记录时出错: {e}")
        finally:
            conn.close()

# ==========================================
# ========== 雷电间击环境数据库功能 ==========
# ==========================================
def excel_bulk_file_management():
    """
    型号 Excel 统计表管理功能
    支持：整表二进制存储、多 Sheet 预览、自动类型修复、删除与导出
    """
    st.markdown("### 📁 型号 Excel 统计台账管理")
    st.info("说明：此功能将整个 Excel 文件（含所有 Sheet）存入数据库，适用于不规则的统计台账。")

    # 确保数据库表已存在
    conn = create_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS aircraft_excel_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aircraft_model TEXT NOT NULL,
            filename TEXT,
            excel_data BLOB,
            description TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.close()

    sub_op = st.tabs(["📊 查看与操作", "📤 上传新表格"])

    # --- Tab 1: 查看与操作 ---
    with sub_op[0]:
        conn = create_connection()
        # 获取索引列表
        df_list = pd.read_sql_query(
            "SELECT id, aircraft_model, filename, description, upload_date FROM aircraft_excel_tables ORDER BY upload_date DESC",
            conn
        )
        conn.close()

        if df_list.empty:
            st.warning("数据库中暂无存档的 Excel 表格。")
        else:
            st.markdown("#### 已存档列表")
            st.dataframe(df_list, use_container_width=True, hide_index=True)

            st.markdown("---")
            col_sel, col_del = st.columns([3, 1])

            with col_sel:
                selected_id = st.selectbox(
                    "选择要操作的记录",
                    df_list['id'],
                    format_func=lambda
                        x: f"ID: {x} | {df_list[df_list['id'] == x]['aircraft_model'].iloc[0]} - {df_list[df_list['id'] == x]['filename'].iloc[0]}"
                )

            # 获取选中文件的详细数据
            conn = create_connection()
            res = conn.execute("SELECT excel_data, filename, aircraft_model FROM aircraft_excel_tables WHERE id=?",
                               (selected_id,)).fetchone()
            conn.close()

            if res:
                excel_bytes, fname, amodel = res

                # 删除功能
                with col_del:
                    st.write("")  # 间距
                    if st.button("🗑️ 删除该记录", type="secondary", use_container_width=True):
                        conn = create_connection()
                        conn.execute("DELETE FROM aircraft_excel_tables WHERE id=?", (selected_id,))
                        conn.commit()
                        conn.close()
                        st.toast(f"已删除记录 ID: {selected_id}", icon="✅")
                        st.rerun()

                # 预览与导出区域
                expander = st.expander(f"查看详情: {fname}", expanded=True)
                with expander:
                    try:
                        xl = pd.ExcelFile(io.BytesIO(excel_bytes))
                        sheet_names = xl.sheet_names

                        c1, c2 = st.columns([2, 1])
                        with c1:
                            sel_sheet = st.selectbox("选择要预览的分表 (Sheet)", sheet_names)
                        with c2:
                            st.write("")  # 间距
                            st.download_button(
                                label="📥 导出原始 Excel",
                                data=excel_bytes,
                                file_name=fname,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

                        # 读取并修复类型冲突
                        raw_df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=sel_sheet)

                        # --- 核心修复：解决 ArrowTypeError ---
                        display_df = raw_df.copy()
                        for col in display_df.columns:
                            # 如果是 object 类型（通常是混合类型或含有特殊格式）
                            if display_df[col].dtype == 'object':
                                # 强制转为字符串，并将 'nan' 替换为空值
                                display_df[col] = display_df[col].astype(str).replace(['nan', 'None', 'NaN'], '')
                        # ------------------------------------

                        st.dataframe(display_df, use_container_width=True)

                    except Exception as e:
                        st.error(f"解析 Excel 失败: {e}")

    # --- Tab 2: 上传新表格 ---
    with sub_op[1]:
        with st.form("upload_excel_form", clear_on_submit=True):
            st.markdown("#### 填写存档信息")
            u_model = st.text_input("飞机型号*", placeholder="例如: AG600")
            u_file = st.file_uploader("选择 Excel 文件", type=["xlsx", "xls"])
            u_desc = st.text_area("内容描述/备注", placeholder="说明该表格的主要内容，如：某次试验的原始记录汇总")

            submit = st.form_submit_button("🚀 提交存档", use_container_width=True)

            if submit:
                if not u_model or not u_file:
                    st.error("请填写必填项（型号和文件）")
                else:
                    conn = create_connection()
                    try:
                        binary_data = u_file.getvalue()
                        conn.execute('''
                            INSERT INTO aircraft_excel_tables (aircraft_model, filename, excel_data, description)
                            VALUES (?, ?, ?, ?)
                        ''', (u_model, u_file.name, binary_data, u_desc))
                        conn.commit()
                        st.success(f"机型 {u_model} 的表格 '{u_file.name}' 已成功存入数据库！")
                    except Exception as e:
                        st.error(f"存储失败: {e}")
                    finally:
                        conn.close()
                    st.success("存入成功！")
                    # 强制 Streamlit 重新运行，这样切换到“查看” Tab 时数据就是最新的
                    st.rerun()

def indirect_effects_page(operation):
    st.header("雷电间击环境数据库")

    if operation == "查看数据":
        tab_v1, tab_v2 = st.tabs(["波形数据检索", "Excel台账查看"])
        with tab_v1:
            view_indirect_effects()
        with tab_v2:
            excel_bulk_file_management()
    elif operation == "添加数据":
        # 增加了一个新 Tab: "半自动/固定字段批量导入"
        tab1, tab2, tab3, tab4 = st.tabs(["单条添加", "智能解析批量导入", "固定字段批量导入 (推荐)", "Excel表格筛选导入"])

        with tab1:
            add_indirect_effect()
        with tab2:
            batch_add_indirect_effects()  # 原有的智能全解析模式
        with tab3:
            hybrid_batch_add_indirect_effects() # 新增的固定字段混合导入模式
        with tab4:
            excel_bulk_file_management()

    elif operation == "修改数据":
        update_indirect_effect()
    elif operation == "删除数据":
        delete_indirect_effect()


def generate_filename_from_record(record):
    """
    根据记录生成标准化的文件名 (用于单个下载和批量下载)
    """
    # 定义文件名字段顺序
    filename_fields = [
        record['aircraft_model'],  # 1. 飞机型号
        record['test_point'],  # 2. 测试点
        record['current_in_out'],  # 3. 电流入/出点
        record['voltage_probe_point'],  # 4. 远端连接器
        record['waveform_type'],  # 5. 激励波形
        record['test_object_type'],  # 6. 被测对象
        record.get('induced_waveform'),  # 7. 感应波形
        record.get('data_domain'),  # 8. 数据域
        record['data_type'],  # 9. 数据类型
        record['data_unit']  # 10. 单位
    ]

    valid_parts = []
    for field in filename_fields:
        if field:
            s_val = str(field).strip()
            # 清理非法字符
            s_val = s_val.replace('/', '-').replace('\\', '-')
            # 简单的中文翻译 (可选)
            if s_val == 'voltage': s_val = '电压'
            if s_val == 'current': s_val = '电流'
            valid_parts.append(s_val)

    if valid_parts:
        return "_".join(valid_parts) + ".dat"
    else:
        return f"data_record_{record['id']}.dat"


def view_indirect_effects():
    st.subheader("查看雷电间击环境数据")

    # 1. 搜索区域
    col1, col2 = st.columns(2)
    with col1:
        aircraft_model = st.text_input("飞机型号", "")
    with col2:
        test_point = st.text_input("电流探针测试点", "")

    # 初始化 session state
    if 'ie_search_result' not in st.session_state:
        st.session_state['ie_search_result'] = None

    # 2. 查询逻辑
    if st.button("查询"):
        conn = create_connection()
        query = "SELECT * FROM indirect_effects WHERE 1=1"
        params = []
        if aircraft_model:
            query += " AND aircraft_model LIKE ?"
            params.append(f"%{aircraft_model}%")
        if test_point:
            query += " AND test_point LIKE ?"
            params.append(f"%{test_point}%")

        df = pd.read_sql_query(query, conn, params=params if params else None)
        conn.close()
        st.session_state['ie_search_result'] = df

    # 3. 结果显示与操作区域
    if st.session_state['ie_search_result'] is not None:
        df_origin = st.session_state['ie_search_result']

        if df_origin.empty:
            st.warning("没有找到匹配的记录")
        else:
            # === 新增功能：构建带选择框的表格 ===

            # A. 准备数据：复制一份数据，并添加 "选择" 列，默认为 False
            df_display = df_origin.copy()
            df_display.insert(0, "选择", False)

            st.markdown("### 📊 数据列表 (请勾选需要下载的数据)")

            # B. 使用 data_editor 让用户勾选
            # 注意：我们将 data_file (二进制) 排除在显示之外，防止表格卡顿
            edited_df = st.data_editor(
                df_display.drop(columns=['data_file']),
                column_config={
                    "选择": st.column_config.CheckboxColumn("选择", help="勾选以加入批量下载", default=False),
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "aircraft_model": st.column_config.TextColumn("飞机型号", disabled=True),
                    # 其他列默认也可以编辑，为了安全建议设为 disabled，或者只处理“选择”列
                },
                disabled=["id", "aircraft_model", "test_point", "waveform_type"],  # 禁止修改关键信息
                hide_index=True,
                use_container_width=True
            )

            # C. 获取用户选中的行
            selected_rows = edited_df[edited_df["选择"] == True]

            # === 批量下载逻辑 ===
            with st.expander("📦 批量下载操作区", expanded=True):
                col_btn, col_info = st.columns([1, 2])

                with col_info:
                    st.info(f"当前筛选结果共 {len(df_origin)} 条，您已勾选 **{len(selected_rows)}** 条。")

                with col_btn:
                    if st.button("生成选中数据的压缩包 (ZIP)"):
                        if selected_rows.empty:
                            st.error("请先在上方表格中至少勾选一条数据！")
                        else:
                            # 创建内存中的 ZIP 文件
                            zip_buffer = io.BytesIO()
                            file_count = 0

                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                # 遍历用户选中的行
                                for index, row in selected_rows.iterrows():
                                    # 注意：edited_df 中没有 data_file，需要用 ID 回溯原始数据
                                    # 或者因为行顺序没变，如果没做排序可以直接对应。
                                    # 最稳妥的方法是根据 ID 去原始 df_origin 里找 data_file

                                    original_record = df_origin[df_origin['id'] == row['id']].iloc[0]

                                    if original_record['data_file']:
                                        # 生成文件名
                                        file_name = generate_filename_from_record(original_record)
                                        # 写入 ZIP
                                        zip_file.writestr(file_name, original_record['data_file'])
                                        file_count += 1

                            zip_buffer.seek(0)

                            if file_count > 0:
                                st.success(f"成功打包 {file_count} 个文件！")
                                st.download_button(
                                    label="⬇️ 点击下载 ZIP压缩包",
                                    data=zip_buffer,
                                    file_name="selected_lightning_data.zip",
                                    mime="application/zip"
                                )
                            else:
                                st.warning("您选中的记录中没有包含有效的数据文件。")

            st.markdown("---")
            st.subheader("详细数据视图 (单条查看)")

            # 下面的单条查看逻辑保持不变，用于查看波形
            # ... [此处复用之前的代码逻辑，从 '选择具体的记录查看' 开始] ...

            # 为了代码简洁，请将之前提供的 '详细数据视图' 部分的代码完整粘贴在这里
            # 这里的逻辑不需要变，它依然服务于单条数据的深度分析

            # 重新获取 ID 列表供下拉框使用
            selected_id = st.selectbox(
                "选择记录查看详细波形",  # 修改了提示文案
                df_origin['id'],
                format_func=lambda
                    x: f"ID:{x} - {df_origin[df_origin['id'] == x]['aircraft_model'].iloc[0]} ({df_origin[df_origin['id'] == x]['test_point'].iloc[0]})"
            )

            selected_record = df_origin[df_origin['id'] == selected_id].iloc[0]

            # ... (后续波形绘制和单文件下载代码与上一版完全一致，请直接保留) ...
            # 为保证完整性，简略写出波形绘制的核心部分，实际请用上一版代码:

            if selected_record['data_file'] is not None:
                # [代码省略：解析 data_file]
                # [代码省略：波形显示设置 (线性/对数)]
                # [代码省略：绘图 plt.plot]
                pass
                # (请务必保留这些代码)

                # 在这里重新粘贴上一轮回答中的 解析+绘图 代码
                # ...

                try:
                    # --- A. 解析数据 ---
                    data_text = selected_record['data_file'].decode('utf-8', errors='ignore')
                    data_lines = data_text.split('\n')

                    x_values = []
                    y_values = []

                    for line in data_lines:
                        line = line.replace(',', ' ').strip()
                        if line and not line.startswith(('#', '//', '%', 'Time', 'Freq')):
                            parts = line.split()
                            if len(parts) >= 2:
                                try:
                                    val_x = float(parts[0])
                                    val_y = float(parts[1])
                                    x_values.append(val_x)
                                    y_values.append(val_y)
                                except ValueError:
                                    continue

                    if x_values and y_values:
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
                            y_array = np.array(y_values)
                            eps = 1e-10
                            y_plot = log_factor * np.log10(np.abs(y_array) + eps)
                            ax.plot(x_values, y_plot, color='tab:red', linewidth=1)
                            ylabel_suffix = f"(dB, N={log_factor})"
                        else:
                            ax.plot(x_values, y_values, color='tab:blue', linewidth=1)
                            ylabel_suffix = ""

                        if selected_record.get('data_domain') == '频域数据':
                            ax.set_xlabel('频率 (MHz)')
                        else:
                            ax.set_xlabel('时间 (s)')

                        unit = selected_record['data_unit'] or ''
                        d_type = selected_record['data_type']
                        y_label_text = "电压" if d_type == 'voltage' else "电流"
                        ax.set_ylabel(f'{y_label_text} {unit} {ylabel_suffix}')
                        ax.set_title(f"{selected_record['aircraft_model']} - {selected_record['test_point']}")
                        ax.grid(True, linestyle='--', alpha=0.6, which='both')
                        st.pyplot(fig)

                        # 单文件下载按钮
                        final_filename = generate_filename_from_record(selected_record)
                        st.download_button(
                            label=f"📥 下载该数据文件 ({final_filename})",
                            data=selected_record['data_file'],
                            file_name=final_filename,
                            mime="application/octet-stream",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"处理数据文件时出错: {e}")
            else:
                st.info("该记录没有上传数据文件")
    else:
        st.info("请输入搜索条件并点击查询按钮")


def add_indirect_effect():
    st.subheader("添加雷电间击环境数据 (支持文件名自动识别)")

    # 1. 预先声明需要自动填充的变量默认值
    parsed_info = {
        "aircraft_model": "",
        "test_point": "",
        "current_in_out": "",
        "voltage_probe_point": "",
        "waveform_type": "A波",
        "induced_waveform": "A波",
        "test_object_type": "线束",
        "data_domain": "时域数据",
        "data_type": "voltage",
        "data_unit": "V"
    }

    # 2. 放在最前面的文件上传器，用于触发识别
    uploaded_file = st.file_uploader("📂 首先上传数据文件以自动识别字段 (.txt/.dat)", type=["txt", "dat"])

    if uploaded_file:
        # 调用您已有的智能解析函数
        parsed_info = smart_parse_filename(uploaded_file.name)
        st.success(f"已识别文件名：{uploaded_file.name}，已为您自动填充下方表单。")

    # 3. 使用容器展示表单，允许用户手动修改识别结果
    with st.container(border=True):
        st.markdown("### 确认并完善记录详情")

        aircraft_model = st.text_input("飞机型号*", value=parsed_info.get("aircraft_model", ""))
        test_point = st.text_input("测试点/连接器编号*", value=parsed_info.get("test_point", ""))

        col1, col2 = st.columns(2)
        with col1:
            current_in_out = st.text_input("实验电流入点/出点", value=parsed_info.get("current_in_out", ""))

            # 计算下拉框的默认索引
            exc_idx = 1 if parsed_info.get("waveform_type") == "H波" else 0
            excitation_waveform = st.selectbox("激励波形", ["A波", "H波"], index=exc_idx)

            ind_idx = 1 if parsed_info.get("induced_waveform") == "H波" else 0
            induced_waveform = st.selectbox("感应波形", ["A波", "H波"], index=ind_idx)

        with col2:
            voltage_probe_point = st.text_input("远端连接器编号", value=parsed_info.get("voltage_probe_point", ""))

            obj_idx = 1 if parsed_info.get("test_object_type") == "针脚" else 0
            test_object_type = st.selectbox("被测对象类型", ["线束", "针脚"], index=obj_idx)

            dom_idx = 1 if parsed_info.get("data_domain") == "频域数据" else 0
            data_domain = st.selectbox("数据域类型", ["时域数据", "频域数据"], index=dom_idx)

        st.markdown("---")

        # 数据类型与单位的动态联动
        col_type, col_unit = st.columns(2)
        with col_type:
            # 确定 Radio 的默认值
            type_idx = 1 if parsed_info.get("data_type") == "current" else 0
            data_type_label = st.radio(
                "数据类型*",
                ["电压数据 (Voltage)", "电流数据 (Current)"],
                index=type_idx,
                horizontal=True,
                key="single_add_type"
            )
            data_type = "voltage" if "Voltage" in data_type_label else "current"

        with col_unit:
            if data_type == "voltage":
                unit_opts = ["kV", "V", "mV"]
            else:
                unit_opts = ["kA", "A", "mA"]

            # 匹配解析出的单位索引
            try:
                u_idx = unit_opts.index(parsed_info.get("data_unit"))
            except:
                u_idx = 1  # 默认 V 或 A

            data_unit = st.selectbox("数据单位*", unit_opts, index=u_idx)

        description = st.text_area("描述", value=parsed_info.get("description", ""))

        submitted = st.button("🚀 提交数据并入库", type="primary", use_container_width=True)

    # 4. 提交逻辑
    if submitted:
        if not aircraft_model or not test_point:
            st.error("飞机型号和测试点是必填项")
            return

        conn = create_connection()
        cursor = conn.cursor()
        try:
            data_bytes = uploaded_file.getvalue() if uploaded_file else None

            cursor.execute(
                '''INSERT INTO indirect_effects (
                    aircraft_model, test_point, current_in_out, voltage_probe_point, 
                    waveform_type, induced_waveform, test_object_type, data_file, 
                    data_type, data_unit, description, data_domain
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (aircraft_model, test_point, current_in_out, voltage_probe_point,
                 excitation_waveform, induced_waveform, test_object_type, data_bytes,
                 data_type, data_unit, description, data_domain)
            )

            conn.commit()
            st.success(f"数据 '{aircraft_model}-{test_point}' 已成功添加！")
            # 自动刷新以清空界面
            st.rerun()
        except Exception as e:
            st.error(f"添加失败: {e}")
        finally:
            conn.close()




def update_indirect_effect():
    st.subheader("修改雷电间击环境数据")

    conn = create_connection()
    df = pd.read_sql_query("SELECT id, aircraft_model, test_point FROM indirect_effects", conn)

    if df.empty:
        st.warning("数据库中没有记录可供修改")
        conn.close()
        return

    selected_id = st.selectbox("选择要修改的记录", df['id'], format_func=lambda
        x: f"ID: {x} - {df[df['id'] == x]['aircraft_model'].iloc[0]} ({df[df['id'] == x]['test_point'].iloc[0]})")

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM indirect_effects WHERE id = ?", (selected_id,))
    record = cursor.fetchone()

    col_names = [description[0] for description in cursor.description]
    rec_dict = dict(zip(col_names, record))

    if not rec_dict:
        st.error("未找到选定的记录")
        conn.close()
        return

    # 使用容器包裹，视觉整洁
    with st.container(border=True):
        st.markdown(f"### 编辑 ID: {selected_id} 的信息")

        aircraft_model = st.text_input("飞机型号*", rec_dict.get('aircraft_model'))
        test_point = st.text_input("电流探针测试点*", rec_dict.get('test_point'))

        col1, col2 = st.columns(2)
        with col1:
            current_in_out = st.text_input("实验电流入点/出点", rec_dict.get('current_in_out') or "")

            exc_idx = 1 if rec_dict.get('waveform_type') == "H波" else 0
            excitation_waveform = st.selectbox("激励波形", ["A波", "H波"], index=exc_idx)

            ind_idx = 1 if rec_dict.get('induced_waveform') == "H波" else 0
            induced_waveform = st.selectbox("感应波形", ["A波", "H波"], index=ind_idx)

        with col2:
            voltage_probe_point = st.text_input("电压探针测试点", rec_dict.get('voltage_probe_point') or "")

            obj_idx = 1 if rec_dict.get('test_object_type') == "针脚" else 0
            test_object_type = st.selectbox("被测对象类型", ["线束", "针脚"], index=obj_idx)

            dom_idx = 1 if rec_dict.get('data_domain') == "频域数据" else 0
            data_domain = st.selectbox("数据域类型", ["时域数据", "频域数据"], index=dom_idx)

        st.markdown("---")
        # === 交互核心区域 ===
        col_type, col_unit = st.columns([1, 1])

        # 1. 确定 Radio 的默认值
        curr_type = rec_dict.get('data_type')
        # 如果数据库是 current，选中第1项(索引1)，否则第0项
        radio_idx = 1 if curr_type == "current" else 0

        with col_type:
            data_type_label = st.radio(
                "数据类型*",
                ["电压数据 (Voltage)", "电流数据 (Current)"],
                index=radio_idx,
                horizontal=True,
                key="update_type_radio"
            )
            data_type = "voltage" if "Voltage" in data_type_label else "current"

        # 2. 动态生成单位
        with col_unit:
            if data_type == "voltage":
                unit_options = ["kV", "V", "mV"]
            else:
                unit_options = ["kA", "A", "mA"]

            # 3. 确定单位的默认值
            curr_unit = rec_dict.get('data_unit')
            try:
                # 只有当 现有单位 在 新生成的列表 中时，才保持选中
                u_idx = unit_options.index(curr_unit)
            except (ValueError, TypeError):
                # 否则重置为默认 (V 或 A)
                u_idx = 1 if len(unit_options) > 1 else 0

            data_unit = st.selectbox("数据单位*", unit_options, index=u_idx, key="update_unit_select")
        # ===================

        data_file = st.file_uploader("上传新数据文件 (.txt/.dat, 留空保持原文件)", type=["txt", "dat"])
        description = st.text_area("描述", rec_dict.get('description') or "")

        # 提交按钮
        submitted = st.button("更新数据", type="primary", use_container_width=True)

    if submitted:
        try:
            if data_file is not None:
                data_bytes = data_file.read()
            else:
                data_bytes = rec_dict.get('data_file')

            cursor.execute(
                '''UPDATE indirect_effects SET 
                    aircraft_model=?, test_point=?, current_in_out=?, voltage_probe_point=?, 
                    waveform_type=?, induced_waveform=?, test_object_type=?, data_file=?, 
                    data_type=?, data_unit=?, description=?, data_domain=? 
                WHERE id=?''',
                (aircraft_model, test_point, current_in_out, voltage_probe_point,
                 excitation_waveform, induced_waveform, test_object_type, data_bytes,
                 data_type, data_unit, description, data_domain, selected_id)
            )

            conn.commit()
            st.success("数据更新成功!")
            # 可选: st.rerun() 刷新页面显示最新数据
        except Exception as e:
            st.error(f"更新数据时出错: {e}")
        finally:
            conn.close()




def delete_indirect_effect():
    st.subheader("删除雷电间击环境数据")
    conn = create_connection()
    df = pd.read_sql_query("SELECT id, aircraft_model, test_point FROM indirect_effects", conn)

    if df.empty:
        st.warning("数据库中没有记录可供删除")
        conn.close()
        return

    selected_id = st.selectbox("选择要删除的记录", df['id'], format_func=lambda
        x: f"ID: {x} - {df[df['id'] == x]['aircraft_model'].iloc[0]} ({df[df['id'] == x]['test_point'].iloc[0]})")

    if st.button("确认删除"):
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM indirect_effects WHERE id = ?", (selected_id,))
            conn.commit()
            st.success("记录删除成功!")
            st.rerun()
        except Exception as e:
            st.error(f"删除记录时出错: {e}")
        finally:
            conn.close()


def batch_add_indirect_effects():
    st.markdown("### 批量数据文件导入 (.dat / .txt)")
    st.info("💡 提示：支持标准模式（8段）或全字段模式（10段，含电流入/出点及远端连接器）。\n"
            "例如：**AG600_TP01_LeftWing_Conn2_A波激励_A波感应_线束_电流_mA_时域.dat**")

    # 1. 文件上传
    uploaded_files = st.file_uploader("将文件拖拽至此 (支持多选)", type=["txt", "dat"], accept_multiple_files=True)

    if not uploaded_files:
        if 'batch_data_cache' in st.session_state:
            del st.session_state['batch_data_cache']
        return

    # 建立文件映射
    file_map = {file.name: file for file in uploaded_files}

    # 2. 解析逻辑 (带缓存)
    if 'batch_data_cache' not in st.session_state or len(st.session_state['batch_data_cache']) != len(uploaded_files):
        data_list = []
        for file in uploaded_files:
            # 调用解析函数
            smart_info = smart_parse_filename(file.name)

            # 构建行数据
            row_data = {
                "文件名": file.name,
                "飞机型号": smart_info.get("aircraft_model", ""),
                "测试点": smart_info.get("test_point", ""),

                # === 修正点：不再硬编码为空，而是读取解析结果 ===
                "电流入/出点": smart_info.get("current_in_out", ""),
                "远端连接器": smart_info.get("voltage_probe_point", ""),
                # ============================================

                "激励波形": smart_info.get("waveform_type", "A波"),
                "感应波形": smart_info.get("induced_waveform", "A波"),
                "被测对象": smart_info.get("test_object_type", "线束"),

                "数据域": smart_info.get("data_domain", "时域数据"),
                "数据类型": smart_info.get("data_type", "voltage"),
                "单位": smart_info.get("data_unit", "V"),
                "描述": smart_info.get("description", "")
            }
            data_list.append(row_data)

        st.session_state['batch_data_cache'] = pd.DataFrame(data_list)

    df = st.session_state['batch_data_cache']

    # 3. 配置可编辑表格
    column_config = {
        "文件名": st.column_config.TextColumn("文件名", disabled=True, help="原始文件名"),
        "飞机型号": st.column_config.TextColumn("飞机型号*", required=True),
        "测试点": st.column_config.TextColumn("测试点*", required=True),
        # 这两个字段现在会自动填入，但也允许用户修改
        "电流入/出点": st.column_config.TextColumn("电流入/出点"),
        "远端连接器": st.column_config.TextColumn("远端连接器"),
        "激励波形": st.column_config.SelectboxColumn("激励波形", options=["A波", "H波"], required=True),
        "感应波形": st.column_config.SelectboxColumn("感应波形", options=["A波", "H波"], required=True),
        "被测对象": st.column_config.SelectboxColumn("被测对象", options=["线束", "针脚"], required=True),
        "数据域": st.column_config.SelectboxColumn("数据域", options=["时域数据", "频域数据"], required=True),
        "数据类型": st.column_config.SelectboxColumn("类型", options=["voltage", "current"], required=True),
        "单位": st.column_config.SelectboxColumn("单位", options=["V", "kV", "mV", "A", "kA", "mA"], required=True),
        "描述": st.column_config.TextColumn("描述")
    }

    st.markdown("⬇️ **预览与修正 (请在下方表格确认自动识别结果):**")
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed"
    )

    # 4. 提交逻辑
    if st.button(f"🚀 确认入库 ({len(uploaded_files)} 个文件)", type="primary"):
        success_count = 0
        fail_count = 0
        conn = create_connection()
        cursor = conn.cursor()

        progress_bar = st.progress(0)

        try:
            total = len(edited_df)
            for index, row in edited_df.iterrows():
                progress_bar.progress((index + 1) / total)

                # 必填校验
                if not row["飞机型号"] or not row["测试点"]:
                    st.toast(f"文件 {row['文件名']} 缺少飞机型号或测试点，已跳过。", icon="⚠️")
                    fail_count += 1
                    continue

                # 获取文件二进制流
                file_obj = file_map.get(row["文件名"])
                if not file_obj:
                    fail_count += 1
                    continue

                file_obj.seek(0)
                data_bytes = file_obj.read()

                try:
                    cursor.execute(
                        '''INSERT INTO indirect_effects (
                            aircraft_model, test_point, current_in_out, voltage_probe_point, 
                            waveform_type, induced_waveform, test_object_type, data_file, 
                            data_type, data_unit, description, data_domain
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            row["飞机型号"],
                            row["测试点"],
                            row["电流入/出点"],  # 现在这里会有值了
                            row["远端连接器"],  # 这里也会有值了
                            row["激励波形"],
                            row["感应波形"],
                            row["被测对象"],
                            data_bytes,
                            row["数据类型"],
                            row["单位"],
                            row["描述"],
                            row["数据域"]
                        )
                    )
                    success_count += 1
                except Exception as e:
                    print(e)
                    fail_count += 1

            conn.commit()

            if success_count > 0:
                st.balloons()
                st.success(f"操作完成！成功导入 {success_count} 条数据。")
                if fail_count > 0:
                    st.warning(f"有 {fail_count} 条数据因信息不全导入失败。")

                if 'batch_data_cache' in st.session_state:
                    del st.session_state['batch_data_cache']
            else:
                st.error("导入失败，请检查表格数据是否完整。")

        except Exception as e:
            st.error(f"数据库错误: {e}")
        finally:
            conn.close()
            progress_bar.empty()


def hybrid_batch_add_indirect_effects():
    st.markdown("### 📌 固定字段 + 文件名动态提取导入")
    st.info("💡 提示：在下方设置本次导入的**共同字段**。如果某个字段留空或选择`<从文件名提取>`，系统将按照规定的 **10个字段顺序** 依次从文件名（以下划线 `_` 分隔）中提取填补缺失项。")

    EXTRACT_FLAG = "<从文件名提取>"

    # === 1. 固定字段设置区域 ===
    with st.expander("⚙️ 设置本批次固定字段 (展开/折叠)", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            ui_model = st.text_input("1. 飞机型号", placeholder="留空则从文件名提取")
            ui_test_point = st.text_input("2. 测试点编号", placeholder="留空则从文件名提取")
            ui_current_io = st.text_input("3. 电流入/出点", placeholder="留空则从文件名提取")

            st.markdown("---")
            # 特殊控制：是否包含远端连接器
            has_remote_conn = st.toggle("本批次包含 '4. 远端连接器' 字段", value=False)
            ui_remote_conn = ""
            if has_remote_conn:
                ui_remote_conn = st.text_input("4. 远端连接器", placeholder="留空则从文件名提取")

        with col2:
            ui_exc = st.selectbox("5. 激励波形", [EXTRACT_FLAG, "A波", "H波"])
            ui_ind = st.selectbox("6. 感应波形", [EXTRACT_FLAG, "A波", "H波"])
            ui_obj = st.selectbox("7. 被测对象", [EXTRACT_FLAG, "线束", "针脚"])

        with col3:
            ui_type = st.selectbox("8. 数据类型", [EXTRACT_FLAG, "voltage", "current"])
            ui_unit = st.selectbox("9. 单位", [EXTRACT_FLAG, "V", "kV", "mV", "A", "kA", "mA"])
            ui_domain = st.selectbox("10. 数据域", [EXTRACT_FLAG, "时域数据", "频域数据"])
            ui_desc = st.text_input("统一备注/描述", value="固定字段批量导入")

    # === 2. 文件上传区域 ===
    uploaded_files = st.file_uploader("📂 选择数据文件 (.txt/.dat，支持多选)", type=["txt", "dat"], accept_multiple_files=True,
                                      key="hybrid_uploader")

    if not uploaded_files:
        if 'hybrid_batch_cache' in st.session_state:
            del st.session_state['hybrid_batch_cache']
        return

    file_map = {file.name: file for file in uploaded_files}

    # === 3. 提取逻辑核心 ===
    if 'hybrid_batch_cache' not in st.session_state or len(st.session_state['hybrid_batch_cache']) != len(
            uploaded_files):
        data_list = []
        for file in uploaded_files:
            # 去除后缀并按 _ 分割
            name_no_ext = file.name.rsplit('.', 1)[0]
            parts = name_no_ext.split('_')
            part_idx = 0

            # 内部辅助函数：按顺序拿取文件名中的下一个有效片段
            def get_next_part():
                nonlocal part_idx
                if part_idx < len(parts):
                    val = parts[part_idx]
                    part_idx += 1
                    return val.strip()
                return ""

            row_data = {"文件名": file.name}

            # 严格按照 10 个字段的顺序提取：
            # 1. 飞机型号
            row_data["飞机型号"] = ui_model if ui_model else get_next_part()
            # 2. 测试点编号
            row_data["测试点"] = ui_test_point if ui_test_point else get_next_part()
            # 3. 电流入/出点
            row_data["电流入/出点"] = ui_current_io if ui_current_io else get_next_part()

            # 4. 远端连接器 (根据开关决定是否占用一个位置)
            if has_remote_conn:
                row_data["远端连接器"] = ui_remote_conn if ui_remote_conn else get_next_part()
            else:
                row_data["远端连接器"] = ""

            # 5. 激励波形
            row_data["激励波形"] = ui_exc if ui_exc != EXTRACT_FLAG else get_next_part()
            # 6. 感应波形
            row_data["感应波形"] = ui_ind if ui_ind != EXTRACT_FLAG else get_next_part()
            # 7. 被测对象
            row_data["被测对象"] = ui_obj if ui_obj != EXTRACT_FLAG else get_next_part()

            # 8. 数据类型 (做简单中英映射以兼容数据库)
            raw_type = ui_type if ui_type != EXTRACT_FLAG else get_next_part()
            if "电压" in raw_type or "VOLTAGE" in raw_type.upper():
                row_data["数据类型"] = "voltage"
            elif "电流" in raw_type or "CURRENT" in raw_type.upper():
                row_data["数据类型"] = "current"
            else:
                row_data["数据类型"] = raw_type

            # 9. 单位
            row_data["单位"] = ui_unit if ui_unit != EXTRACT_FLAG else get_next_part()

            # 10. 数据域
            raw_domain = ui_domain if ui_domain != EXTRACT_FLAG else get_next_part()
            if "频" in raw_domain or "FREQ" in raw_domain.upper():
                row_data["数据域"] = "频域数据"
            elif "时" in raw_domain or "TIME" in raw_domain.upper():
                row_data["数据域"] = "时域数据"
            else:
                row_data["数据域"] = raw_domain

            row_data["描述"] = ui_desc
            data_list.append(row_data)

        st.session_state['hybrid_batch_cache'] = pd.DataFrame(data_list)

    df = st.session_state['hybrid_batch_cache']

    # === 4. 数据确认与编辑表格 ===
    st.markdown("⬇️ **提取结果预览 (可直接在表格中双击单元格修改):**")

    # 设置列格式以提供下拉选择框，防止非法输入
    column_config = {
        "文件名": st.column_config.TextColumn("文件名", disabled=True),
        "激励波形": st.column_config.SelectboxColumn("激励波形", options=["A波", "H波"]),
        "感应波形": st.column_config.SelectboxColumn("感应波形", options=["A波", "H波"]),
        "被测对象": st.column_config.SelectboxColumn("被测对象", options=["线束", "针脚"]),
        "数据类型": st.column_config.SelectboxColumn("类型", options=["voltage", "current"]),
        "单位": st.column_config.SelectboxColumn("单位", options=["V", "kV", "mV", "A", "kA", "mA"]),
        "数据域": st.column_config.SelectboxColumn("数据域", options=["时域数据", "频域数据"])
    }

    edited_df = st.data_editor(df, column_config=column_config, use_container_width=True, hide_index=True)

    # === 5. 入库操作 ===
    if st.button(f"🚀 确认无误，将这 {len(uploaded_files)} 条数据入库", type="primary"):
        success_count, fail_count = 0, 0
        conn = create_connection()
        cursor = conn.cursor()
        progress_bar = st.progress(0)

        try:
            total = len(edited_df)
            for index, row in edited_df.iterrows():
                progress_bar.progress((index + 1) / total)

                # 必填项简单校验
                if not row["飞机型号"] or not row["测试点"]:
                    st.toast(f"文件 {row['文件名']} 缺少必填的型号或测试点，已跳过。", icon="⚠️")
                    fail_count += 1
                    continue

                file_obj = file_map.get(row["文件名"])
                if not file_obj:
                    fail_count += 1
                    continue

                file_obj.seek(0)
                data_bytes = file_obj.read()

                try:
                    cursor.execute(
                        '''INSERT INTO indirect_effects (
                            aircraft_model, test_point, current_in_out, voltage_probe_point, 
                            waveform_type, induced_waveform, test_object_type, data_file, 
                            data_type, data_unit, description, data_domain
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            row["飞机型号"], row["测试点"], row["电流入/出点"], row["远端连接器"],
                            row["激励波形"], row["感应波形"], row["被测对象"], data_bytes,
                            row["数据类型"], row["单位"], row["描述"], row["数据域"]
                        )
                    )
                    success_count += 1
                except Exception as e:
                    print(e)
                    fail_count += 1

            conn.commit()

            if success_count > 0:
                st.balloons()
                st.success(f"🎉 批量导入成功！共入库 {success_count} 条数据。")
                if fail_count > 0:
                    st.warning(f"有 {fail_count} 条数据导入失败，请检查必填项是否完整。")

                # 成功后清理缓存
                if 'hybrid_batch_cache' in st.session_state:
                    del st.session_state['hybrid_batch_cache']
            else:
                st.error("导入失败。请检查预览表格中的信息是否完整合法。")

        except Exception as e:
            st.error(f"数据库操作异常: {e}")
        finally:
            conn.close()
            progress_bar.empty()

def smart_parse_filename(filename):
    """
    智能解析文件名 (修复波形识别逻辑版)
    解决 A波/H波 同时出现时的识别混淆问题。
    """
    name_no_ext = filename.rsplit('.', 1)[0]
    parts = name_no_ext.split('_')
    full_str = name_no_ext.upper()

    info = {}

    # === 1. 基础字段解析 (模式 A/B) ===
    info["aircraft_model"] = ""
    info["test_point"] = ""
    info["current_in_out"] = ""
    info["voltage_probe_point"] = ""

    if len(parts) >= 10:
        # 模式 B: 全字段
        info["aircraft_model"] = parts[0]
        info["test_point"] = parts[1]
        info["current_in_out"] = parts[2]
        info["voltage_probe_point"] = parts[3]
    elif len(parts) >= 2:
        # 模式 A: 标准
        info["aircraft_model"] = parts[0]
        info["test_point"] = parts[1]
    else:
        info["aircraft_model"] = name_no_ext

    # === 2. 波形识别核心逻辑 (重大修改) ===

    # 步骤 A: 提取所有出现的波形 (保持在文件名中的出现顺序)
    # 例如 "AG600_A波_H波.dat" -> ['A波', 'H波']
    all_waves = re.findall(r'([AHah]波)', name_no_ext)
    all_waves = [w.upper() for w in all_waves]  # 统一转大写

    # 步骤 B: 尝试寻找显式的 "X波激励" 和 "X波感应"
    explicit_exc = re.search(r'([AHah]波)激励', name_no_ext)
    explicit_ind = re.search(r'([AHah]波)感应', name_no_ext)

    # 步骤 C: 判定激励波形
    if explicit_exc:
        # 情况1: 明确写了 "A波激励"
        info["waveform_type"] = explicit_exc.group(1).upper()
    elif len(all_waves) >= 1:
        # 情况2: 没明确写，但找到了波形，默认第1个是激励
        info["waveform_type"] = all_waves[0]
    else:
        # 情况3: 啥都没找到，默认A波
        info["waveform_type"] = "A波"

    # 步骤 D: 判定感应波形
    if explicit_ind:
        # 情况1: 明确写了 "H波感应"
        info["induced_waveform"] = explicit_ind.group(1).upper()
    elif len(all_waves) >= 2:
        # 情况2: 没明确写，但找到了2个波形 (例如 A波_H波)，默认第2个是感应
        # 注意：这里要处理一种情况，就是文件名只有 "A波激励_线束"，all_waves=['A波']，此时不应把感应设为H
        if explicit_exc and len(all_waves) == 1:
            # 如果只有一个波且已用于激励，感应同激励
            info["induced_waveform"] = info["waveform_type"]
        else:
            # 否则取第二个
            info["induced_waveform"] = all_waves[1]
    else:
        # 情况3: 只有一个波或没有波，默认感应 = 激励
        info["induced_waveform"] = info.get("waveform_type", "A波")

    # === 3. 其他字段解析 (保持不变) ===

    # --- 被测对象 ---
    if "线束" in name_no_ext or "CABLE" in full_str:
        info["test_object_type"] = "线束"
    elif "针脚" in name_no_ext or "PIN" in full_str:
        info["test_object_type"] = "针脚"
    else:
        info["test_object_type"] = "线束"

    # --- 数据域 ---
    if "频域" in name_no_ext or "FREQ" in full_str:
        info["data_domain"] = "频域数据"
    else:
        info["data_domain"] = "时域数据"

    # --- 数据类型 ---
    if "电压" in name_no_ext or "VOLTAGE" in full_str:
        info["data_type"] = "voltage"
    elif "电流" in name_no_ext or "CURRENT" in full_str:
        info["data_type"] = "current"
    else:
        info["data_type"] = "voltage"

    # --- 单位 ---
    info["data_unit"] = "V"
    if info["data_type"] == "voltage":
        if "KV" in full_str:
            info["data_unit"] = "kV"
        elif "MV" in full_str:
            info["data_unit"] = "mV"
        elif "V" in full_str:
            info["data_unit"] = "V"
    else:
        if "KA" in full_str:
            info["data_unit"] = "kA"
        elif "MA" in full_str:
            info["data_unit"] = "mA"
        elif "A" in full_str:
            info["data_unit"] = "A"

    info["description"] = "批量导入"

    return info


def smart_parse_filename00(filename):
    """
    智能解析文件名 (增强版)
    支持:
    1. 模式 A (标准8段): 飞机型号_测试点_任意描述...
    2. 模式 B (全字段10段): 飞机型号_测试点_入出点_远端_激励_感应_对象_类型_单位_域
    3. 灵活匹配: 解决如 "A波_H波" 这种简写无法识别感应波形的问题
    """
    name_no_ext = filename.rsplit('.', 1)[0]
    # 替换中文空格或其他特殊分隔符为标准下划线，提高鲁棒性
    name_no_ext = name_no_ext.replace(' ', '_').replace('__', '_')
    parts = name_no_ext.split('_')
    full_str = name_no_ext.upper()

    info = {}

    # === 1. 位置解析 (优先提取) ===
    info["aircraft_model"] = parts[0] if len(parts) >= 1 else name_no_ext
    info["test_point"] = parts[1] if len(parts) >= 2 else ""
    info["current_in_out"] = ""
    info["voltage_probe_point"] = ""

    # 全字段模式识别 (模式 B)
    if len(parts) >= 10:
        info["current_in_out"] = parts[2]
        info["voltage_probe_point"] = parts[3]
        # 在全字段模式下，位置是最高优先级的
        info["waveform_type"] = parts[4].replace("激励", "")
        info["induced_waveform"] = parts[5].replace("感应", "")

    # === 2. 关键词智能提取/修正 (针对简写情况优化) ===

    # --- 激励波形识别 ---
    # 如果位置解析没拿到，或者想二次确认
    if "waveform_type" not in info:
        if "H波激励" in name_no_ext or "H波" in parts:  # 增加对独立 "H波" 段的判断
            info["waveform_type"] = "H波"
        else:
            info["waveform_type"] = "A波"  # 默认为A波

    # --- 感应波形识别 (核心修改点) ---
    if "induced_waveform" not in info:
        # 1. 寻找显式包含 "感应" 的段
        found_induced = False
        for p in parts:
            if "感应" in p:
                info["induced_waveform"] = "H波" if "H" in p.upper() else "A波"
                found_induced = True
                break

        # 2. 如果没找到 "感应" 字样，但存在多个波形描述 (如示例中的 A波_H波)
        if not found_induced:
            # 统计文件名中波形出现的次数
            wave_parts = [p for p in parts if p in ["A波", "H波", "A波激励", "H波激励", "A波感应", "H波感应"]]
            if len(wave_parts) >= 2:
                # 假设第二个出现的波形是感应波形
                info["induced_waveform"] = "H波" if "H" in wave_parts[1].upper() else "A波"
            else:
                # 兜底逻辑：同激励波形
                info["induced_waveform"] = info["waveform_type"]

    # --- 其余字段识别 (被测对象/数据域/类型/单位) ---
    # 被测对象
    info["test_object_type"] = "针脚" if ("针脚" in name_no_ext or "PIN" in full_str) else "线束"

    # 数据域
    info["data_domain"] = "频域数据" if ("频域" in name_no_ext or "FREQ" in full_str) else "时域数据"

    # 类型与单位
    if "电流" in name_no_ext or "CURRENT" in full_str or "A" in parts or "MA" in full_str:
        info["data_type"] = "current"
        info["data_unit"] = "mA" if "MA" in full_str else ("kA" if "KA" in full_str else "A")
    else:
        info["data_type"] = "voltage"
        info["data_unit"] = "mV" if "MV" in full_str else ("kV" if "KV" in full_str else "V")

    info["description"] = "批量导入"
    return info




# 关于页面
def about_page():
    st.header("关于")
    st.write("""
    ### 飞机雷电分区和雷电间击环境数据库系统
    本系统用于管理飞机雷电分区和雷电间击环境的仿真测试数据。

    **功能更新:**
    - 支持雷电间击环境时域/频域数据切换 (.dat/.txt)
    - 支持激励波形和感应波形 (A波/H波) 的分类管理
    """)


def fix_database_structure():
    """
    用于修复数据库表结构的临时函数。
    解决 CHECK constraint failed: waveform_type IN ('A波', 'h波') 问题。
    """
    db_path = 'aircraft_lightning.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. 检查是否存在旧表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='indirect_effects'")
        if not cursor.fetchone():
            print("表 indirect_effects 不存在，无需修复。")
            return

        print("开始修复数据库表结构...")

        # 2. 将现有表重命名为备份表
        cursor.execute("ALTER TABLE indirect_effects RENAME TO indirect_effects_backup")

        # 3. 创建新表 (使用正确的约束或移除约束)
        # 注意：这里我们移除了 waveform_type 的 CHECK 约束，以防万一，并在代码层面控制
        cursor.execute('''
        CREATE TABLE indirect_effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aircraft_model TEXT NOT NULL,
            test_point TEXT NOT NULL,
            current_in_out TEXT,
            voltage_probe_point TEXT,
            waveform_type TEXT,  -- 激励波形 (已移除错误的 CHECK 约束)
            test_object_type TEXT,
            data_file BLOB,
            data_type TEXT,
            data_unit TEXT,
            description TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_domain TEXT,      -- 确保包含新字段
            induced_waveform TEXT  -- 确保包含新字段
        )
        ''')

        # 4. 将数据从备份表迁移回来
        # 注意：我们需要动态获取备份表的列，以防止列名不匹配
        cursor.execute("PRAGMA table_info(indirect_effects_backup)")
        columns_info = cursor.fetchall()
        # 获取旧表中存在的列名
        old_columns = [col[1] for col in columns_info]

        # 构建插入语句的列名部分 (只迁移新旧表都存在的列)
        # 定义新表的所有列
        new_columns = [
            'id', 'aircraft_model', 'test_point', 'current_in_out', 'voltage_probe_point',
            'waveform_type', 'test_object_type', 'data_file', 'data_type', 'data_unit',
            'description', 'upload_date', 'data_domain', 'induced_waveform'
        ]

        # 找出交集列
        common_columns = [col for col in new_columns if col in old_columns]
        columns_str = ", ".join(common_columns)

        insert_sql = f"INSERT INTO indirect_effects ({columns_str}) SELECT {columns_str} FROM indirect_effects_backup"
        cursor.execute(insert_sql)

        # 5. 删除备份表 (如果你想保险一点，可以先注释掉这行)
        cursor.execute("DROP TABLE indirect_effects_backup")

        conn.commit()
        print("✅ 数据库表结构修复成功！错误的 CHECK 约束已移除。")
        st.success("数据库自动修复完成！现在可以重新尝试导入数据了。")

    except Exception as e:
        conn.rollback()
        st.error(f"修复数据库时出错: {e}")
        print(f"修复失败: {e}")
    finally:
        conn.close()


# === 请在 main() 函数的最开始调用一次这个函数 ===
# fix_database_structure()

main()