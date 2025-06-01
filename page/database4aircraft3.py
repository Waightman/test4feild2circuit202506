import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO


# 创建或连接数据库
def create_connection(db_file):
    """创建数据库连接"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        st.error(f"数据库连接错误: {e}")
    return conn


# 初始化数据库表
def init_db(conn):
    """初始化数据库表"""
    try:
        cursor = conn.cursor()

        # 创建感应电流表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS induced_current (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aircraft_model TEXT NOT NULL,
            current_probe TEXT NOT NULL,
            antenna_point TEXT NOT NULL,
            data_content TEXT NOT NULL,
            frequency_unit TEXT NOT NULL,
            notes TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 创建感应电场表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS induced_field (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aircraft_model TEXT NOT NULL,
            current_probe TEXT NOT NULL,
            antenna_point TEXT NOT NULL,
            data_content TEXT NOT NULL,
            frequency_unit TEXT NOT NULL,
            notes TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
    except sqlite3.Error as e:
        st.error(f"数据库初始化错误: {e}")


# 解析数据文件
def parse_data_file(uploaded_file):
    """解析上传的文件内容"""
    try:
        # 读取文件内容为字符串
        content = uploaded_file.getvalue().decode("utf-8")
        return content
    except Exception as e:
        st.error(f"解析数据文件错误: {e}")
        return None


# 转换频率到MHz
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
        return freq  # 默认认为是MHz


# 验证频率范围
def validate_frequency_range(data_content, frequency_unit, table_name):
    """验证频率范围是否符合要求"""
    try:
        # 读取数据为DataFrame
        df = pd.read_csv(StringIO(data_content), sep='\t' if '\t' in data_content else ',', header=None)
        if df.shape[1] < 1:
            return False, "数据文件需要至少包含频率列"

        # 获取频率列
        frequencies = df.iloc[:, 0]

        # 检查频率列是否为数值
        if not pd.api.types.is_numeric_dtype(frequencies):
            return False, "频率列必须为数值"

        # 转换为MHz单位
        frequencies_mhz = frequencies.apply(lambda x: convert_to_mhz(x, frequency_unit))

        # 检查频率范围
        if table_name == "induced_current":
            min_freq, max_freq = 1, 400  # 1MHz~400MHz
            data_type = "感应电流"
        else:  # induced_field
            min_freq, max_freq = 100, 8000  # 100MHz~8GHz
            data_type = "感应电磁"

        # 检查最小值
        if frequencies_mhz.min() < min_freq:
            return False, (f"{data_type}数据频率范围应为{min_freq}MHz~{max_freq}MHz\n"
                           f"检测到最小频率: {frequencies_mhz.min()}MHz (低于下限{min_freq}MHz)")

        # 检查最大值
        if frequencies_mhz.max() > max_freq:
            return False, (f"{data_type}数据频率范围应为{min_freq}MHz~{max_freq}MHz\n"
                           f"检测到最大频率: {frequencies_mhz.max()}MHz (超过上限{max_freq}MHz)")

        return True, "频率范围验证通过"
    except Exception as e:
        return False, f"频率验证错误: {e}"


# 绘制数据曲线
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

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(data.iloc[:, 0], data.iloc[:, 1])
        ax.set_xlabel('Frequency')
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True)
        st.pyplot(fig)
    except Exception as e:
        st.error(f"绘图错误: {e}")


# 添加数据记录
def add_record(conn, table_name, record):
    """添加新记录"""
    try:
        cursor = conn.cursor()
        cursor.execute(f'''
        INSERT INTO {table_name} 
        (aircraft_model, current_probe, antenna_point, data_content, frequency_unit, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', record)
        conn.commit()
        st.success("记录添加成功!")
    except sqlite3.Error as e:
        st.error(f"添加记录错误: {e}")


# 更新数据记录
def update_record(conn, table_name, record_id, new_record):
    """更新记录"""
    try:
        cursor = conn.cursor()
        cursor.execute(f'''
        UPDATE {table_name} 
        SET aircraft_model=?, current_probe=?, antenna_point=?, data_content=?, frequency_unit=?, notes=?
        WHERE id=?
        ''', (*new_record, record_id))
        conn.commit()
        st.success("记录更新成功!")
    except sqlite3.Error as e:
        st.error(f"更新记录错误: {e}")


# 删除数据记录
def delete_record(conn, table_name, record_id):
    """删除记录"""
    try:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM {table_name} WHERE id=?', (record_id,))
        conn.commit()
        st.success("记录删除成功!")
    except sqlite3.Error as e:
        st.error(f"删除记录错误: {e}")


# 查询数据记录
def query_records(conn, table_name, conditions=None):
    """查询记录"""
    try:
        cursor = conn.cursor()

        if conditions:
            query = f'SELECT * FROM {table_name} WHERE '
            query += ' AND '.join([f"{k}=?" for k in conditions.keys()])
            cursor.execute(query, tuple(conditions.values()))
        else:
            cursor.execute(f'SELECT * FROM {table_name}')

        columns = [column[0] for column in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return records
    except sqlite3.Error as e:
        st.error(f"查询记录错误: {e}")
        return []


# 生成下载文件
def generate_download_file(record):
    """生成要下载的文件内容"""
    try:
        # 创建文件名
        filename = f"{record['aircraft_model']}_{record['current_probe']}_{record['antenna_point']}.txt"

        # 获取数据内容
        data_content = record['data_content']

        return filename, data_content
    except Exception as e:
        st.error(f"生成下载文件错误: {e}")
        return None, None


# 主页面
def main():
    st.title("飞机HIRF环境数据库系统")

    # 数据库连接
    db_file = "aircraft_hirf.db"
    conn = create_connection(db_file)
    if conn is not None:
        init_db(conn)
    else:
        st.error("无法连接到数据库!")
        return

    # 侧边栏导航
    st.sidebar.title("导航")
    menu = ["感应电流数据库 (1MHz~400MHz)", "感应电场数据库 (100MHz~8GHz)", "关于"]
    database_type = st.sidebar.selectbox("导航", menu)

    operation = st.sidebar.radio(
        "选择操作",
        ("查询数据", "添加数据", "修改数据", "删除数据")
    )

    # 根据选择的数据库类型设置参数
    if "感应电流" in database_type:
        table_name = "induced_current"
        ylabel = "Current (A)"
        freq_range = "1MHz~400MHz"
    else:
        table_name = "induced_field"
        ylabel = "Field Strength (V/m)"
        freq_range = "100MHz~8GHz"

    # 查询数据
    if operation == "查询数据":
        st.header(f"{database_type} - 查询数据")

        # 查询条件
        col1, col2, col3 = st.columns(3)
        with col1:
            aircraft_model = st.text_input("飞机型号", "")
        with col2:
            current_probe = st.text_input("电流探针", "")
        with col3:
            antenna_point = st.text_input("天线测试点", "")

        conditions = {}
        if aircraft_model:
            conditions["aircraft_model"] = aircraft_model
        if current_probe:
            conditions["current_probe"] = current_probe
        if antenna_point:
            conditions["antenna_point"] = antenna_point

        # 执行查询
        if st.button("查询"):
            records = query_records(conn, table_name, conditions if conditions else None)

            if records:
                st.subheader("查询结果")
                # 显示简化的记录信息
                display_cols = ['id', 'aircraft_model', 'current_probe', 'antenna_point', 'frequency_unit',
                                'upload_time']
                df = pd.DataFrame(records)[display_cols]
                st.dataframe(df)

                # 选择要查看的记录
                record_ids = [str(r['id']) for r in records]
                selected_id = st.selectbox("选择记录查看详细数据", record_ids)
                selected_record = next(r for r in records if str(r['id']) == selected_id)

                # 显示详细信息和数据曲线
                st.subheader("记录详情")
                st.json({k: v for k, v in selected_record.items() if k != 'data_content'})

                # 绘制数据曲线
                plot_data(selected_record['data_content'],
                          f"{database_type} - {selected_record['aircraft_model']}",
                          ylabel)

                # 添加下载按钮
                st.subheader("数据下载")
                filename, file_content = generate_download_file(selected_record)
                if filename and file_content:
                    st.download_button(
                        label="下载数据为TXT文件",
                        data=file_content,
                        file_name=filename,
                        mime="text/plain"
                    )
            else:
                st.warning("没有找到匹配的记录")

    # 添加数据
    elif operation == "添加数据":
        st.header(f"{database_type} - 添加数据")

        with st.form("add_form"):
            col1, col2 = st.columns(2)
            with col1:
                aircraft_model = st.text_input("飞机型号*", "")
                current_probe = st.text_input("电流探针*", "")
            with col2:
                antenna_point = st.text_input("天线测试点*", "")
                # 频率单位选择
                freq_units = ["Hz", "KHz", "MHz", "GHz"]
                default_index = 2 if "感应电流" in database_type else 3  # 默认MHz或GHz
                frequency_unit = st.selectbox("频率单位*", freq_units, index=default_index)

            data_file = st.file_uploader("上传数据文件 (TXT格式)*", type=['txt'])
            notes = st.text_area("备注", "")

            submitted = st.form_submit_button("提交")

            if submitted:
                if not all([aircraft_model, current_probe, antenna_point, data_file]):
                    st.error("带*的字段为必填项!")
                else:
                    # 解析文件内容
                    data_content = parse_data_file(data_file)
                    if data_content:
                        # 验证频率范围
                        is_valid, msg = validate_frequency_range(data_content, frequency_unit, table_name)
                        if not is_valid:
                            st.error(f"数据验证失败: {msg}")
                            st.warning("请检查数据文件并重新上传")
                        else:
                            record = (aircraft_model, current_probe, antenna_point,
                                      data_content, frequency_unit, notes)
                            add_record(conn, table_name, record)

    # 修改数据
    elif operation == "修改数据":
        st.header(f"{database_type} - 修改数据")

        # 先查询所有记录供选择
        records = query_records(conn, table_name)
        if records:
            record_ids = [str(r['id']) for r in records]
            selected_id = st.selectbox("选择要修改的记录", record_ids)
            selected_record = next(r for r in records if str(r['id']) == selected_id)

            with st.form("update_form"):
                col1, col2 = st.columns(2)
                with col1:
                    aircraft_model = st.text_input("飞机型号*", selected_record['aircraft_model'])
                    current_probe = st.text_input("电流探针*", selected_record['current_probe'])
                with col2:
                    antenna_point = st.text_input("天线测试点*", selected_record['antenna_point'])
                    # 频率单位选择
                    freq_units = ["Hz", "KHz", "MHz", "GHz"]
                    current_unit_index = freq_units.index(selected_record['frequency_unit'])
                    frequency_unit = st.selectbox("频率单位*", freq_units, index=current_unit_index)

                st.text("当前数据:")
                plot_data(selected_record['data_content'],
                          f"当前数据 - {selected_record['aircraft_model']}",
                          ylabel)

                new_data_file = st.file_uploader("上传新数据文件 (TXT格式)", type=['txt'])
                notes = st.text_area("备注", selected_record['notes'])

                submitted = st.form_submit_button("更新")

                if submitted:
                    if not all([aircraft_model, current_probe, antenna_point]):
                        st.error("带*的字段为必填项!")
                    else:
                        # 如果上传了新文件，使用新文件；否则保留原数据
                        data_content = selected_record['data_content']
                        if new_data_file:
                            data_content = parse_data_file(new_data_file)
                            if data_content:
                                # 验证新数据的频率范围
                                is_valid, msg = validate_frequency_range(data_content, frequency_unit, table_name)
                                if not is_valid:
                                    st.error(f"数据验证失败: {msg}")
                                    st.warning("请检查数据文件并重新上传")
                                    return

                        new_record = (aircraft_model, current_probe, antenna_point,
                                      data_content, frequency_unit, notes)
                        update_record(conn, table_name, selected_record['id'], new_record)
        else:
            st.warning("数据库中没有记录")

    # 删除数据
    elif operation == "删除数据":
        st.header(f"{database_type} - 删除数据")

        # 先查询所有记录供选择
        records = query_records(conn, table_name)
        if records:
            record_ids = [str(r['id']) for r in records]
            selected_id = st.selectbox("选择要删除的记录", record_ids)
            selected_record = next(r for r in records if str(r['id']) == selected_id)

            st.warning("以下记录将被删除，此操作不可恢复!")
            st.json({k: v for k, v in selected_record.items() if k != 'data_content'})

            if st.button("确认删除"):
                delete_record(conn, table_name, selected_record['id'])
        else:
            st.warning("数据库中没有记录")

    # 关闭数据库连接
    conn.close()
main()