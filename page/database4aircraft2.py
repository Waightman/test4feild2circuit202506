import streamlit as st
import sqlite3
import os
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import io


# 创建或连接数据库
def create_connection():
    conn = sqlite3.connect('aircraft_lightning.db')
    return conn


# 初始化数据库表
def init_db():
    conn = create_connection()
    cursor = conn.cursor()

    # 创建雷电分区表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS lightning_zones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aircraft_model TEXT NOT NULL,
        zone_image BLOB,
        description TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 创建雷电间击环境表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS indirect_effects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aircraft_model TEXT NOT NULL,
        test_point TEXT NOT NULL,
        data_file BLOB,
        data_type TEXT CHECK(data_type IN ('voltage', 'current')),
        description TEXT,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()


# 初始化数据库
init_db()


# 主页面
def main():
    st.title("飞机雷电分区和雷电间击环境数据库系统")

    # 侧边栏导航
    menu = ["雷电分区数据库", "雷电间击环境数据库", "关于"]
    choice = st.sidebar.selectbox("导航", menu)
    # 操作选项
    operation = st.sidebar.radio("选择操作", ["查看数据", "添加数据", "修改数据", "删除数据"])
    if choice == "雷电分区数据库":
        lightning_zones_page(operation)
    elif choice == "雷电间击环境数据库":
        indirect_effects_page(operation)
    else:
        about_page()


# 雷电分区数据库页面
def lightning_zones_page(operation):
    st.header("雷电分区数据库")

    # # 操作选项
    # operation = st.radio("选择操作", ["查看数据", "添加数据", "修改数据", "删除数据"])

    if operation == "查看数据":
        view_lightning_zones()
    elif operation == "添加数据":
        add_lightning_zone()
    elif operation == "修改数据":
        update_lightning_zone()
    elif operation == "删除数据":
        delete_lightning_zone()


# 雷电间击环境数据库页面
def indirect_effects_page(operation):
    st.header("雷电间击环境数据库")

    # # 操作选项
    # operation = st.radio("选择操作", ["查看数据", "添加数据", "修改数据", "删除数据"])

    if operation == "查看数据":
        view_indirect_effects()
    elif operation == "添加数据":
        add_indirect_effect()
    elif operation == "修改数据":
        update_indirect_effect()
    elif operation == "删除数据":
        delete_indirect_effect()


# 关于页面
def about_page():
    st.header("关于")
    st.write("""
    ### 飞机雷电分区和雷电间击环境数据库系统

    本系统用于管理飞机雷电分区和雷电间击环境的仿真测试数据。

    **功能包括:**
    - 雷电分区图片的存储和管理
    - 雷电间击环境仿真数据的存储和管理
    - 数据查询、添加、修改和删除

    **开发人员:** [您的姓名]
    """)


# ========== 雷电分区数据库功能 ==========

def view_lightning_zones():
    st.subheader("查看雷电分区数据")

    # 搜索选项
    aircraft_model = st.text_input("输入飞机型号进行搜索", "")

    conn = create_connection()

    if aircraft_model:
        query = "SELECT * FROM lightning_zones WHERE aircraft_model LIKE ?"
        params = (f"%{aircraft_model}%",)
    else:
        query = "SELECT * FROM lightning_zones"
        params = ()

    df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        st.warning("没有找到匹配的记录")
    else:
        st.dataframe(df.drop(columns=['zone_image']))

        # 显示选中的图片
        selected_id = st.selectbox("选择记录查看图片", df['id'])

        selected_record = df[df['id'] == selected_id].iloc[0]

        if selected_record['zone_image'] is not None:
            try:
                image = Image.open(io.BytesIO(selected_record['zone_image']))
                st.image(image, caption=f"飞机型号: {selected_record['aircraft_model']}")
            except:
                st.error("无法显示图片")
        else:
            st.warning("该记录没有图片")

        st.write(f"描述: {selected_record['description']}")
        st.write(f"上传日期: {selected_record['upload_date']}")

    conn.close()


def add_lightning_zone():
    st.subheader("添加雷电分区数据")

    with st.form("add_lightning_zone_form"):
        aircraft_model = st.text_input("飞机型号*", "")
        image_file = st.file_uploader("上传分区图片", type=["jpg", "jpeg", "png"])
        description = st.text_area("描述", "")

        submitted = st.form_submit_button("提交")

        if submitted:
            if not aircraft_model:
                st.error("飞机型号是必填项")
                return

            conn = create_connection()
            cursor = conn.cursor()

            try:
                if image_file is not None:
                    image_bytes = image_file.read()
                else:
                    image_bytes = None

                cursor.execute(
                    "INSERT INTO lightning_zones (aircraft_model, zone_image, description) VALUES (?, ?, ?)",
                    (aircraft_model, image_bytes, description)
                )

                conn.commit()
                st.success("数据添加成功!")
            except Exception as e:
                st.error(f"添加数据时出错: {e}")
            finally:
                conn.close()


def update_lightning_zone():
    st.subheader("修改雷电分区数据")

    conn = create_connection()
    df = pd.read_sql_query("SELECT id, aircraft_model FROM lightning_zones", conn)

    if df.empty:
        st.warning("数据库中没有记录可供修改")
        conn.close()
        return

    selected_id = st.selectbox("选择要修改的记录", df['id'],
                               format_func=lambda x: f"ID: {x} - {df[df['id'] == x]['aircraft_model'].iloc[0]}")

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lightning_zones WHERE id = ?", (selected_id,))
    record = cursor.fetchone()

    if not record:
        st.error("未找到选定的记录")
        conn.close()
        return

    with st.form("update_lightning_zone_form"):
        aircraft_model = st.text_input("飞机型号*", record[1])
        image_file = st.file_uploader("上传新分区图片 (留空保持原图)", type=["jpg", "jpeg", "png"])
        description = st.text_area("描述", record[3] or "")

        submitted = st.form_submit_button("更新")

        if submitted:
            if not aircraft_model:
                st.error("飞机型号是必填项")
                return

            try:
                if image_file is not None:
                    image_bytes = image_file.read()
                else:
                    # 保持原图不变
                    image_bytes = record[2]

                cursor.execute(
                    "UPDATE lightning_zones SET aircraft_model = ?, zone_image = ?, description = ? WHERE id = ?",
                    (aircraft_model, image_bytes, description, selected_id)
                )

                conn.commit()
                st.success("数据更新成功!")
            except Exception as e:
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

    st.warning(f"您确定要删除飞机型号为 '{record[0]}' 的记录吗?")

    if st.button("确认删除"):
        try:
            cursor.execute("DELETE FROM lightning_zones WHERE id = ?", (selected_id,))
            conn.commit()
            st.success("记录删除成功!")
        except Exception as e:
            st.error(f"删除记录时出错: {e}")
        finally:
            conn.close()


# ========== 雷电间击环境数据库功能 ==========

def view_indirect_effects():
    st.subheader("查看雷电间击环境数据")

    # 搜索选项
    col1, col2 = st.columns(2)
    with col1:
        aircraft_model = st.text_input("飞机型号", "")
    with col2:
        test_point = st.text_input("电流探针测试点", "")

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

    if df.empty:
        st.warning("没有找到匹配的记录")
    else:
        st.dataframe(df.drop(columns=['data_file']))

        # 显示选中的数据
        selected_id = st.selectbox("选择记录查看数据", df['id'])

        selected_record = df[df['id'] == selected_id].iloc[0]

        if selected_record['data_file'] is not None:
            try:
                # 尝试解析数据文件为二维曲线
                data_text = selected_record['data_file'].decode('utf-8')
                data_lines = data_text.split('\n')

                # 解析数据为频率和电压/电流值
                frequencies = []
                values = []

                for line in data_lines:
                    if line.strip() and not line.startswith('#'):  # 忽略注释和空行
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                freq = float(parts[0])
                                val = float(parts[1])
                                frequencies.append(freq)
                                values.append(val)
                            except ValueError:
                                continue

                if frequencies and values:
                    # 绘制曲线图
                    fig, ax = plt.subplots()
                    ax.plot(frequencies, values)
                    ax.set_xlabel('频率 (Hz)')
                    ax.set_ylabel('电压 (V)' if selected_record['data_type'] == 'voltage' else '电流 (A)')
                    ax.set_title(f"飞机型号: {selected_record['aircraft_model']}\n测试点: {selected_record['test_point']}")
                    ax.grid(True)

                    st.pyplot(fig)
                else:
                    st.warning("无法解析数据文件内容")

                # 提供下载链接
                st.download_button(
                    label="下载数据文件",
                    data=selected_record['data_file'],
                    file_name=f"{selected_record['aircraft_model']}_{selected_record['test_point']}.txt",
                    mime="text/plain"
                )
            except Exception as e:
                st.error(f"显示数据时出错: {e}")
        else:
            st.warning("该记录没有数据文件")

        st.write(f"数据类型: {selected_record['data_type']}")
        st.write(f"描述: {selected_record['description']}")
        st.write(f"上传日期: {selected_record['upload_date']}")

    conn.close()


def add_indirect_effect():
    st.subheader("添加雷电间击环境数据")

    with st.form("add_indirect_effect_form"):
        aircraft_model = st.text_input("飞机型号*", "")
        test_point = st.text_input("电流探针测试点*", "")
        data_file = st.file_uploader("上传数据文件 (TXT格式)", type=["txt"])
        data_type = st.selectbox("数据类型*", ["voltage", "current"],
                                 format_func=lambda x: "电压" if x == "voltage" else "电流")
        description = st.text_area("描述", "")

        submitted = st.form_submit_button("提交")

        if submitted:
            if not aircraft_model or not test_point or not data_type:
                st.error("带*的字段是必填项")
                return

            conn = create_connection()
            cursor = conn.cursor()

            try:
                if data_file is not None:
                    data_bytes = data_file.read()
                else:
                    data_bytes = None

                cursor.execute(
                    "INSERT INTO indirect_effects (aircraft_model, test_point, data_file, data_type, description) VALUES (?, ?, ?, ?, ?)",
                    (aircraft_model, test_point, data_bytes, data_type, description)
                )

                conn.commit()
                st.success("数据添加成功!")
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

    if not record:
        st.error("未找到选定的记录")
        conn.close()
        return

    with st.form("update_indirect_effect_form"):
        aircraft_model = st.text_input("飞机型号*", record[1])
        test_point = st.text_input("电流探针测试点*", record[2])
        data_file = st.file_uploader("上传新数据文件 (TXT格式, 留空保持原文件)", type=["txt"])
        data_type = st.selectbox("数据类型*", ["voltage", "current"],
                                 index=0 if record[4] == "voltage" else 1,
                                 format_func=lambda x: "电压" if x == "voltage" else "电流")
        description = st.text_area("描述", record[5] or "")

        submitted = st.form_submit_button("更新")

        if submitted:
            if not aircraft_model or not test_point or not data_type:
                st.error("带*的字段是必填项")
                return

            try:
                if data_file is not None:
                    data_bytes = data_file.read()
                else:
                    # 保持原文件不变
                    data_bytes = record[3]

                cursor.execute(
                    "UPDATE indirect_effects SET aircraft_model = ?, test_point = ?, data_file = ?, data_type = ?, description = ? WHERE id = ?",
                    (aircraft_model, test_point, data_bytes, data_type, description, selected_id)
                )

                conn.commit()
                st.success("数据更新成功!")
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

    cursor = conn.cursor()
    cursor.execute("SELECT aircraft_model, test_point FROM indirect_effects WHERE id = ?", (selected_id,))
    record = cursor.fetchone()

    if not record:
        st.error("未找到选定的记录")
        conn.close()
        return

    st.warning(f"您确定要删除飞机型号为 '{record[0]}', 测试点为 '{record[1]}' 的记录吗?")

    if st.button("确认删除"):
        try:
            cursor.execute("DELETE FROM indirect_effects WHERE id = ?", (selected_id,))
            conn.commit()
            st.success("记录删除成功!")
        except Exception as e:
            st.error(f"删除记录时出错: {e}")
        finally:
            conn.close()



main()