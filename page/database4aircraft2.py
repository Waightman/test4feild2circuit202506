import streamlit as st
import sqlite3
import os
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import io
import re
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

def indirect_effects_page(operation):
    st.header("雷电间击环境数据库")

    # 修改这里，增加 "批量添加"
    if operation == "查看数据":
        view_indirect_effects()
    elif operation == "添加数据":
        # 使用 tabs 分开单条添加和批量添加，体验更好
        tab1, tab2 = st.tabs(["单条添加", "批量文件导入"])
        with tab1:
            add_indirect_effect()
        with tab2:
            batch_add_indirect_effects()  # 新增的函数
    elif operation == "修改数据":
        update_indirect_effect()
    elif operation == "删除数据":
        delete_indirect_effect()


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
        # 动态构建 SQL 语句
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

    # 3. 结果显示区域
    if st.session_state['ie_search_result'] is not None:
        df = st.session_state['ie_search_result']
        if df.empty:
            st.warning("没有找到匹配的记录")
        else:
            # 显示概览表格 (隐藏二进制文件列)
            st.dataframe(df.drop(columns=['data_file']), use_container_width=True)

            st.markdown("---")
            st.subheader("详细数据视图")

            # 选择具体的记录查看
            # 使用 format_func 让下拉框显示更友好的信息
            selected_id = st.selectbox(
                "选择记录查看详细波形和下载",
                df['id'],
                format_func=lambda
                    x: f"ID:{x} - {df[df['id'] == x]['aircraft_model'].iloc[0]} ({df[df['id'] == x]['test_point'].iloc[0]})"
            )

            # 获取选中记录的完整数据
            selected_record = df[df['id'] == selected_id].iloc[0]

            # 解析字段 (兼容旧数据可能缺失的情况)
            data_domain = selected_record.get('data_domain')
            induced_waveform = selected_record.get('induced_waveform')
            excitation_waveform = selected_record['waveform_type']

            # 显示元数据
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.write(f"**激励波形**: {excitation_waveform or '未填写'}")
                st.write(f"**感应波形**: {induced_waveform or '未填写'}")
            with col_info2:
                st.write(f"**数据域**: {data_domain or '未填写'}")
                st.write(f"**对象类型**: {selected_record['test_object_type'] or '未填写'}")
            with col_info3:
                st.write(f"**电流入/出点**: {selected_record['current_in_out'] or '未填写'}")
                st.write(f"**电压探针**: {selected_record['voltage_probe_point'] or '未填写'}")

            # 4. 数据文件处理 (绘图 & 下载)
            if selected_record['data_file'] is not None:
                try:
                    # --- A. 尝试解析并绘图 ---
                    data_text = selected_record['data_file'].decode('utf-8', errors='ignore')
                    data_lines = data_text.split('\n')

                    x_values = []
                    y_values = []

                    for line in data_lines:
                        line = line.replace(',', ' ').strip()
                        # 跳过注释行和空行
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
                        fig, ax = plt.subplots(figsize=(10, 4))
                        ax.plot(x_values, y_values)

                        # 设置坐标轴标签
                        if data_domain == '频域数据':
                            ax.set_xlabel('频率 (MHz)')
                        else:
                            ax.set_xlabel('时间 (s)')

                        unit = selected_record['data_unit'] or ''
                        d_type = selected_record['data_type']
                        # 简单的翻译映射
                        y_label_text = "电压" if d_type == 'voltage' else "电流"
                        ax.set_ylabel(f'{y_label_text} ({unit})')

                        ax.set_title(f"{selected_record['aircraft_model']} - {selected_record['test_point']}")
                        ax.grid(True, linestyle='--', alpha=0.6)
                        st.pyplot(fig)
                    else:
                        st.warning("无法从文件中解析出有效的 X-Y 数据对，无法绘图。")

                    # --- B. 智能生成文件名并下载 ---

                    # 定义文件名字段顺序 (严格按照你的格式要求)
                    filename_fields = [
                        selected_record['aircraft_model'],  # 1. 飞机型号
                        selected_record['test_point'],  # 2. 测试点/连接器编号
                        selected_record['current_in_out'],  # 3. 实验电流入点/出点
                        selected_record['voltage_probe_point'],  # 4. 远端连接器编号
                        selected_record['waveform_type'],  # 5. 激励波形
                        selected_record['test_object_type'],  # 6. 被测对象类型
                        selected_record.get('induced_waveform'),  # 7. 感应波形
                        selected_record.get('data_domain'),  # 8. 数据域类型
                        selected_record['data_type'],  # 9. 数据类型
                        selected_record['data_unit']  # 10. 数据单位
                    ]

                    valid_parts = []
                    for field in filename_fields:
                        if field:  # 只有字段不为空(None或"")时才添加
                            s_val = str(field).strip()
                            # 处理非法字符 (文件名不能包含 / 或 \)
                            s_val = s_val.replace('/', '-').replace('\\', '-')

                            # (可选) 将 voltage/current 翻译为中文，保持与输入文件名风格一致
                            if s_val == 'voltage': s_val = '电压'
                            if s_val == 'current': s_val = '电流'

                            valid_parts.append(s_val)

                    # 拼接文件名
                    if valid_parts:
                        # 检测原文件是 .txt 还是 .dat (通过前面解析时的逻辑，或者默认 .dat)
                        # 这里统一保存为 .dat，或者根据内容判断
                        final_filename = "_".join(valid_parts) + ".dat"
                    else:
                        final_filename = "unknown_data.dat"

                    st.download_button(
                        label=f"📥 下载数据文件 ({final_filename})",
                        data=selected_record['data_file'],
                        file_name=final_filename,
                        mime="application/octet-stream",
                        use_container_width=True
                    )

                except Exception as e:
                    st.error(f"处理数据文件时出错: {e}")
            else:
                st.info("该记录没有上传数据文件")

            # 显示描述
            if selected_record['description']:
                st.markdown(f"**描述信息:**\n> {selected_record['description']}")
    else:
        st.info("请输入搜索条件并点击查询按钮")


def add_indirect_effect():
    st.subheader("添加雷电间击环境数据")

    # 使用带边框的容器，视觉上像 Form，但允许内部交互
    with st.container(border=True):
        st.markdown("### 新增记录详情")

        aircraft_model = st.text_input("飞机型号*", "")
        test_point = st.text_input("测试点/连接器编号*", "")

        col1, col2 = st.columns(2)
        with col1:
            current_in_out = st.text_input("实验电流入点/出点", "")
            excitation_waveform = st.selectbox("激励波形", ["A波", "H波"])
            induced_waveform = st.selectbox("感应波形", ["A波", "H波"])
        with col2:
            voltage_probe_point = st.text_input("远端连接器编号", "")
            test_object_type = st.selectbox("被测对象类型", ["线束", "针脚"])
            data_domain = st.selectbox("数据域类型", ["时域数据", "频域数据"])

        st.markdown("---")
        # === 交互核心区域 ===
        col_type, col_unit = st.columns([1, 1])
        with col_type:
            # 使用横向 Radio，比下拉框更好看，且容易理解是“二选一”
            # 注意：这里没有 form，所以改变选项会立即触发页面刷新(Rerun)
            data_type_label = st.radio(
                "数据类型*",
                ["电压数据 (Voltage)", "电流数据 (Current)"],
                horizontal=True,
                key="add_type_radio"
            )
            # 解析选择结果
            data_type = "voltage" if "Voltage" in data_type_label else "current"

        with col_unit:
            # 根据左侧的选择，动态生成右侧的选项
            if data_type == "voltage":
                unit_options = ["kV", "V", "mV"]
            else:
                unit_options = ["kA", "A", "mA"]

            data_unit = st.selectbox("数据单位*", unit_options, key="add_unit_select")
        # ===================

        data_file = st.file_uploader("上传数据文件 (.txt/.dat)", type=["txt", "dat"])
        st.caption("文件格式要求：两列数据，第一列为时间(s)或频率(MHz)，第二列为数值")

        description = st.text_area("描述", "")

        # 按钮放在容器内部底部
        submitted = st.button("提交数据", type="primary", use_container_width=True)

    # 逻辑处理：只有点击按钮才执行
    if submitted:
        if not aircraft_model or not test_point:
            st.error("带*的字段是必填项")
            return

        conn = create_connection()
        cursor = conn.cursor()
        try:
            data_bytes = data_file.read() if data_file else None

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
            st.success("数据添加成功!")
            # 可选：稍微延迟后刷新，清空表单
            # import time; time.sleep(1); st.rerun()
        except Exception as e:
            st.error(f"添加数据时出错: {e}")
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
    st.markdown("### 批量数据文件导入")
    st.info("提示：系统会自动根据文件名猜测参数（如：AG600_TP1_电流_kA.dat）。您可以在下方表格中批量修正后提交。")

    # 1. 文件上传
    uploaded_files = st.file_uploader("选择数据文件 (支持多选)", type=["txt", "dat"], accept_multiple_files=True)

    if not uploaded_files:
        # 如果用户取消了选择，清除缓存，避免下次显示旧数据
        if 'batch_data_cache' in st.session_state:
            del st.session_state['batch_data_cache']
        return

    # === 关键步骤：建立映射字典 ===
    # 将文件名映射到文件对象，解决 PyArrow 无法序列化 UploadedFile 的问题
    file_map = {file.name: file for file in uploaded_files}

    # 2. 解析逻辑 (带缓存，防止每次点击页面都重置表格)
    # 只有当缓存不存在，或者缓存的文件数量与当前上传不一致时，才重新解析
    if 'batch_data_cache' not in st.session_state or len(st.session_state['batch_data_cache']) != len(uploaded_files):
        data_list = []
        for file in uploaded_files:
            # 调用智能解析函数
            smart_info = smart_parse_filename(file.name)

            # 构建行数据 (只包含字符串/数字，绝对不要包含 file 对象)
            row_data = {
                "文件名": file.name,  # 这是找回文件对象的 Key
                "飞机型号": smart_info.get("飞机型号", ""),
                "测试点": smart_info.get("测试点", ""),
                "电流入/出点": smart_info.get("电流入/出点", ""),
                "远端连接器": smart_info.get("远端连接器", ""),

                "激励波形": smart_info.get("激励波形", "A波"),
                "被测对象": smart_info.get("被测对象", "线束"),
                "感应波形": smart_info.get("感应波形", "A波"),
                "数据域": smart_info.get("数据域", "时域数据"),
                "数据类型": smart_info.get("数据类型", "voltage"),
                "单位": smart_info.get("单位", "V"),

                "描述": "批量导入"
            }
            data_list.append(row_data)

        st.session_state['batch_data_cache'] = pd.DataFrame(data_list)

    # 3. 显示可编辑表格
    df = st.session_state['batch_data_cache']

    # 配置列编辑器 (Dropdowns 等)
    column_config = {
        "文件名": st.column_config.TextColumn("文件名", disabled=True, width="medium"),  # 禁止改文件名
        "飞机型号": st.column_config.TextColumn("飞机型号", required=True),
        "测试点": st.column_config.TextColumn("测试点", required=True),
        "激励波形": st.column_config.SelectboxColumn("激励波形", options=["A波", "H波"], required=True),
        "被测对象": st.column_config.SelectboxColumn("被测对象", options=["线束", "针脚"], required=True),
        "感应波形": st.column_config.SelectboxColumn("感应波形", options=["A波", "H波"], required=True),
        "数据域": st.column_config.SelectboxColumn("数据域", options=["时域数据", "频域数据"], required=True),
        "数据类型": st.column_config.SelectboxColumn("数据类型", options=["voltage", "current"], required=True),
        "单位": st.column_config.SelectboxColumn("单位", options=["V", "kV", "mV", "A", "kA", "mA"], required=True),
    }

    st.markdown("⬇️ **请确认并完善下方信息 (支持Excel式拖拽修改):**")
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",  # 禁止用户在表格里增加空行，必须通过上传文件增加
        hide_index=True
    )

    # 4. 提交逻辑
    if st.button(f"确认导入 {len(uploaded_files)} 条数据", type="primary"):
        success_count = 0
        fail_count = 0

        conn = create_connection()
        cursor = conn.cursor()

        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            total_rows = len(edited_df)
            for index, row in edited_df.iterrows():
                # 更新进度
                progress = (index + 1) / total_rows
                progress_bar.progress(progress)
                status_text.text(f"正在处理: {row['文件名']}...")

                # 必填检查
                if not row["飞机型号"] or not row["测试点"]:
                    st.toast(f"跳过: {row['文件名']} (缺少型号或测试点)", icon="⚠️")
                    fail_count += 1
                    continue

                # === 核心：从 map 中找回文件对象 ===
                file_name_key = row["文件名"]
                file_obj = file_map.get(file_name_key)

                if file_obj is None:
                    st.error(f"严重错误：找不到原始文件 {file_name_key}")
                    fail_count += 1
                    continue

                # 读取文件内容
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
                    st.error(f"导入 {row['文件名']} 数据库写入失败: {e}")
                    fail_count += 1

            conn.commit()

            # 结果反馈
            if success_count > 0:
                st.balloons()
                st.success(f"处理完成！成功导入: {success_count} 条，失败: {fail_count} 条。")

                # 清除缓存，以便用户可以进行下一批次上传
                if 'batch_data_cache' in st.session_state:
                    del st.session_state['batch_data_cache']

                # 可选：稍微延迟后刷新页面以清空文件上传器
                # import time
                # time.sleep(2)
                # st.rerun()
            else:
                st.error("所有文件均导入失败，请检查数据格式。")

        except Exception as e:
            st.error(f"发生未预期的错误: {e}")
        finally:
            conn.close()
            status_text.empty()
def batch_add_indirect_effects00():
    st.markdown("### 批量数据文件导入")
    st.info("提示：您可以上传多个数据文件。系统将尝试从文件名解析信息。您可以在下方表格中修正数据后统一提交。")

    uploaded_files = st.file_uploader("选择数据文件 (支持多选)", type=["txt", "dat"], accept_multiple_files=True)

    if not uploaded_files:
        return

    # === 关键修改 1: 创建一个文件名到文件对象的映射字典 ===
    # 这样我们就不用把文件对象放进 DataFrame 里了
    file_map = {file.name: file for file in uploaded_files}

    # 缓存解析结果
    if 'batch_data_cache' not in st.session_state or len(st.session_state['batch_data_cache']) != len(uploaded_files):
        data_list = []
        for file in uploaded_files:
            fname = file.name.rsplit('.', 1)[0]
            parts = fname.split('_')

            # === 关键修改 2: row_data 中去掉 "文件对象" ===
            row_data = {
                "文件名": file.name,  # 这里的名字将作为 Key
                "飞机型号": "", "测试点": "", "电流入/出点": "", "远端连接器": "",
                "激励波形": "A波", "被测对象": "线束", "感应波形": "A波",
                "数据域": "时域数据", "数据类型": "voltage", "单位": "V",
                "描述": "批量导入"
                # 注意：这里删除了 "文件对象": file
            }

            # 智能填空逻辑
            if len(parts) >= 1: row_data["飞机型号"] = parts[0]
            if len(parts) >= 2: row_data["测试点"] = parts[1]
            if len(parts) >= 3: row_data["电流入/出点"] = parts[2]
            if len(parts) >= 4: row_data["远端连接器"] = parts[3]

            data_list.append(row_data)

        st.session_state['batch_data_cache'] = pd.DataFrame(data_list)

    df = st.session_state['batch_data_cache']

    # 配置列
    column_config = {
        # === 关键修改 3: 删除 "文件对象" 的配置，因为该列已不存在 ===
        "文件名": st.column_config.TextColumn("文件名", disabled=True),  # 禁止修改文件名，保证能找到对应文件
        "激励波形": st.column_config.SelectboxColumn("激励波形", options=["A波", "H波"], required=True),
        "被测对象": st.column_config.SelectboxColumn("被测对象", options=["线束", "针脚"], required=True),
        "感应波形": st.column_config.SelectboxColumn("感应波形", options=["A波", "H波"], required=True),
        "数据域": st.column_config.SelectboxColumn("数据域", options=["时域数据", "频域数据"], required=True),
        "数据类型": st.column_config.SelectboxColumn("数据类型", options=["voltage", "current"], required=True),
        "单位": st.column_config.SelectboxColumn("单位", options=["V", "kV", "mV", "A", "kA", "mA"], required=True),
    }

    st.markdown("⬇️ **请在下方表格中检查并完善信息 (支持Excel式拖拽复制):**")

    edited_df = st.data_editor(
        df,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True
    )

    if st.button(f"确认导入 {len(uploaded_files)} 条数据", type="primary"):
        success_count = 0
        fail_count = 0

        conn = create_connection()
        cursor = conn.cursor()

        progress_bar = st.progress(0)

        try:
            for index, row in edited_df.iterrows():
                if not row["飞机型号"] or not row["测试点"]:
                    st.warning(f"跳过文件 {row['文件名']}：缺少飞机型号或测试点")
                    fail_count += 1
                    continue

                # === 关键修改 4: 从 file_map 中获取文件对象 ===
                file_name_key = row["文件名"]
                file_obj = file_map.get(file_name_key)

                if file_obj is None:
                    st.error(f"找不到文件对象: {file_name_key}")
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
                    st.error(f"导入 {row['文件名']} 失败: {e}")
                    fail_count += 1

                progress_bar.progress((index + 1) / len(edited_df))

            conn.commit()

            if success_count > 0:
                st.success(f"成功导入 {success_count} 条数据！")
                if fail_count > 0:
                    st.warning(f"{fail_count} 条数据导入失败。")

                del st.session_state['batch_data_cache']
                # 建议在这里让界面刷新，以免进度条卡住或数据残留
                # st.rerun()

        except Exception as e:
            st.error(f"数据库操作严重错误: {e}")
        finally:
            conn.close()



def smart_parse_filename(filename):
    """
    智能解析文件名 (升级版)
    针对格式如: A波激励H波感应电流_C50_频域.dat
    """
    name_no_ext = filename.rsplit('.', 1)[0]
    parts = name_no_ext.split('_')

    info = {}

    # === A. 基础位置解析 ===
    # 假设格式较为固定，但也做好了越界保护
    # 注意：根据你的报错文件名，第一段很长 "A波激励H波感应电流"，它包含了大量信息
    # 真正的 "飞机型号" 似乎没在文件名的第一段体现？或者第一段就是 "A波..."？
    # 如果文件名是 "A波激励H波感应电流_C50_频域.dat"
    # parts[0] = "A波激励H波感应电流"
    # parts[1] = "C50" (可能是测试点?)
    # parts[2] = "频域"

    # 针对你给出的文件名样例进行特殊适配：
    if len(parts) >= 2:
        info["测试点"] = parts[1]  # 假设 C50 是测试点

    # === B. 正则表达式精确提取 (核心优化) ===

    # 1. 提取 激励波形 (匹配 "X波激励" 前面的 X波)
    match_exc = re.search(r'([A-Za-z]波)激励', name_no_ext)
    if match_exc:
        # 提取出来可能是 "A波" 或 "H波"
        info["激励波形"] = match_exc.group(1).upper()  # 自动转大写，防止 "h波"
    else:
        # 如果没写“激励”，但文件名包含 A波/H波，再尝试兜底
        if "A波" in name_no_ext and "H波" not in name_no_ext:
            info["激励波形"] = "A波"
        elif "H波" in name_no_ext and "A波" not in name_no_ext:
            info["激励波形"] = "H波"
        else:
            info["激励波形"] = "A波"  # 默认

    # 2. 提取 感应波形 (匹配 "X波感应" 前面的 X波)
    match_ind = re.search(r'([A-Za-z]波)感应', name_no_ext)
    if match_ind:
        info["感应波形"] = match_ind.group(1).upper()
    else:
        # 如果没明确写“感应”，默认与激励相同
        info["感应波形"] = info.get("激励波形", "A波")

    # 3. 提取 被测对象
    if "线束" in name_no_ext or "Cable" in name_no_ext:
        info["被测对象"] = "线束"
    elif "针脚" in name_no_ext or "Pin" in name_no_ext:
        info["被测对象"] = "针脚"
    else:
        info["被测对象"] = "线束"

    # 4. 提取 数据域
    if "频域" in name_no_ext:
        info["数据域"] = "频域数据"
    else:
        info["数据域"] = "时域数据"

    # 5. 提取 数据类型 & 单位
    if "电压" in name_no_ext or "Voltage" in name_no_ext:
        info["数据类型"] = "voltage"
        if "kV" in name_no_ext:
            info["单位"] = "kV"
        elif "mV" in name_no_ext:
            info["单位"] = "mV"
        else:
            info["单位"] = "V"

    elif "电流" in name_no_ext or "Current" in name_no_ext:
        info["数据类型"] = "current"
        if "kA" in name_no_ext:
            info["单位"] = "kA"
        elif "mA" in name_no_ext:
            info["单位"] = "mA"
        else:
            info["单位"] = "A"
    else:
        info["数据类型"] = "current"  # 根据你的文件名 "感应电流"，默认设为 current 更合理
        info["单位"] = "A"

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