import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import os
import io
import zipfile
import time
from datetime import datetime
from PIL import Image
import matplotlib.pyplot as plt

# 设置 Matplotlib 中文字体 (防止中文乱码)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
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


# ================= 数据库操作模块 =================

def create_connection():
    conn = sqlite3.connect('shielding_design_v2.db')
    conn.execute("PRAGMA foreign_keys = ON")  # 开启外键约束以支持级联删除
    return conn


def init_db():
    conn = create_connection()
    c = conn.cursor()

    # 1. 创建基体材料表
    c.execute('''CREATE TABLE IF NOT EXISTS materials
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  model TEXT,
                  supplier TEXT,
                  standard TEXT)''')

    # 2. 创建主表
    c.execute('''CREATE TABLE IF NOT EXISTS shielding_designs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  test_id TEXT UNIQUE,
                  structure_type TEXT,
                  thickness_summary TEXT,
                  layer_details TEXT,
                  shielding_material TEXT,
                  create_time TIMESTAMP,
                  update_time TIMESTAMP)''')

    # 3. 创建图片存储表
    c.execute('''CREATE TABLE IF NOT EXISTS design_images
                 (img_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  test_id TEXT,
                  image_name TEXT,
                  image_data BLOB,
                  upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (test_id) REFERENCES shielding_designs (test_id) ON DELETE CASCADE)''')

    # 4. 创建12组dat文件存储表
    c.execute('''CREATE TABLE IF NOT EXISTS design_dat_files
                 (file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  test_id TEXT,
                  data_source TEXT,
                  polarization TEXT,
                  data_type TEXT,
                  freq_unit TEXT DEFAULT 'GHz',
                  file_name TEXT,
                  file_data BLOB,
                  upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (test_id) REFERENCES shielding_designs (test_id) ON DELETE CASCADE)''')

    # 数据库结构升级补丁：兼容如果已经存在旧的 design_dat_files 表，自动增加 freq_unit 列
    try:
        c.execute("SELECT freq_unit FROM design_dat_files LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE design_dat_files ADD COLUMN freq_unit TEXT DEFAULT 'GHz'")
        conn.commit()

    # 插入预定义的基体材料数据
    materials_data = [
        ("碳纤维单向带预浸料", "GW300 2-3K-5-8/BA9916", "中航复材", "MS 34D01"),
        ("碳纤维织物预浸料", "GW3011-2-5-8/BA9916", "中航复材", "MS 34D01"),
        ("芳纶纸蜂窝芯", "ACCH-2I-1/8-3.0", "中航复材", "MS 29D01"),
        ("芳纶纸蜂窝芯", "ACCH-2I-1/8-3.0（OX）", "中航复材", "MS 29D01"),
        ("高温胶膜", "J-419B", "黑龙江石化", "MS 24D01"),
        ("泡沫夹芯", "PMI-71", "——", "——"),
        ("7781玻璃纤维", "ACTECH1203/EW301F", "中航复材", "GF AG5100T001C2"),
        ("防雷击胶膜", "J-399-3-141ED", "大连义邦", "MS 35D01"),
        ("防雷击胶膜", "J-399-3-195ED", "大连义邦", "MS 35D01"),
        ("防雷击胶膜", "KKL-CU73LSP-266", "合肥航太", "——"),
        ("防雷击胶膜", "KKL-CU142LSP-266", "合肥航太", "——"),
        ("防雷击胶膜", "KKL-CU115LSP-266", "合肥航太", "——"),
        ("防雷击胶膜", "LSP-C-EP01", "合肥航太", "——"),
        ("防雷击胶膜", "LSP-C-EP02", "合肥航太", "——"),
        ("防雷击胶膜", "HTTM-2", "合肥航太", "——"),
        ("碳膜", "——", "领航复材", "——")
    ]
    c.execute("SELECT COUNT(*) FROM materials")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO materials (name, model, supplier, standard) VALUES (?, ?, ?, ?)", materials_data)

    conn.commit()
    conn.close()


init_db()

# DAT文件的12种固定组合配置
DAT_CONFIGS = [
    ("计算", "HH（水平极化）", "介电常数文件"),
    ("计算", "HH（水平极化）", "电导率文件"),
    ("计算", "HH（水平极化）", "屏蔽效能文件"),
    ("计算", "VV（垂直极化）", "介电常数文件"),
    ("计算", "VV（垂直极化）", "电导率文件"),
    ("计算", "VV（垂直极化）", "屏蔽效能文件"),
    ("测试", "HH（水平极化）", "介电常数文件"),
    ("测试", "HH（水平极化）", "电导率文件"),
    ("测试", "HH（水平极化）", "屏蔽效能文件"),
    ("测试", "VV（垂直极化）", "介电常数文件"),
    ("测试", "VV（垂直极化）", "电导率文件"),
    ("测试", "VV（垂直极化）", "屏蔽效能文件"),
]


def get_materials():
    conn = create_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, model, supplier, standard FROM materials")
    materials = c.fetchall()
    conn.close()
    return materials


def delete_material(material_id):
    conn = create_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM materials WHERE id=?", (material_id,))
        conn.commit()
        return True, "材料删除成功"
    finally:
        conn.close()


def add_material(name, model, supplier, standard):
    conn = create_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO materials (name, model, supplier, standard) VALUES (?, ?, ?, ?)",
                  (name, model, supplier, standard))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_shielding_designs(structure_type=None, thickness=None, shielding_material=None):
    conn = create_connection()
    c = conn.cursor()
    query = """SELECT test_id, structure_type, thickness_summary, layer_details, shielding_material, create_time, update_time
               FROM shielding_designs WHERE 1=1"""
    params = []
    if structure_type:
        query += " AND structure_type = ?"
        params.append(structure_type)
    if thickness:
        query += " AND thickness_summary LIKE ?"
        params.append(f"%{thickness}%")
    if shielding_material:
        query += " AND shielding_material = ?"
        params.append(shielding_material)

    c.execute(query, params)
    designs = c.fetchall()
    conn.close()
    return designs


def clear_query_cache():
    """清理查询页面的缓存，确保数据增删改后展示最新数据"""
    if 'search_results' in st.session_state:
        del st.session_state['search_results']
    if 'delete_search_results' in st.session_state:
        del st.session_state['delete_search_results']


# ================= UI 页面模块 =================

def main():
    LOGO_PATH = "company_logo.jpg"
    logo_base64 = wyz_io.image_to_base64(LOGO_PATH)
    if logo_base64:
        logo_html = f"""
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
            <img src="data:image/jpeg;base64,{logo_base64}" alt="公司标徽" style="height: 60px;">
            <h3 style="margin: 0; font-size: 42px;">中航通飞华南飞机工业有限公司</h3>
        </div>
        """
        st.markdown(logo_html, unsafe_allow_html=True)

    st.title("复合材料飞机结构电磁屏蔽设计数据库系统")

    menu_options = ["添加新设计", "修改设计", "删除设计", "查询设计", "材料管理"]
    choice = st.sidebar.radio("选择操作类型", menu_options)

    materials = get_materials()
    material_options = {f"{m[1]} ({m[2]})": m[0] for m in materials}
    structure_types = ["单向带层板", "织物层板", "织物夹层", "层压", "蜂窝夹层", "泡沫夹层"]
    shielding_materials = ["铜网", "碳基膜", "N/A"]

    if choice == "材料管理":
        manage_materials_page(materials, material_options)
    elif choice == "添加新设计":
        add_design_page(structure_types, shielding_materials, material_options)
    elif choice == "修改设计":
        update_design_page(structure_types, shielding_materials, material_options)
    elif choice == "删除设计":
        delete_design_page(structure_types, shielding_materials)
    elif choice == "查询设计":
        query_design_page(structure_types, materials, shielding_materials)


def manage_materials_page(materials, material_options):
    st.subheader("基体材料管理")
    tab1, tab2 = st.tabs(["添加新材料", "删除材料"])
    with tab1:
        with st.form("add_material_form"):
            name = st.text_input("材料名称*")
            model = st.text_input("牌号*")
            supplier = st.text_input("供应商")
            standard = st.text_input("标准")
            if st.form_submit_button("添加"):
                if not name or not model:
                    st.error("材料名称和牌号为必填项")
                else:
                    if add_material(name, model, supplier, standard):
                        st.success("材料添加成功！请刷新页面。")
                    else:
                        st.error("添加失败，材料可能已存在")
    with tab2:
        if not materials:
            st.warning("无可用材料")
        else:
            material_list = [f"{m[0]}: {m[1]} ({m[2]}) - {m[3]}" for m in materials]
            selected = st.selectbox("选择要删除的材料", material_list)
            if st.button("删除"):
                selected_id = int(selected.split(":")[0])
                success, msg = delete_material(selected_id)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)


def add_design_page(structure_types, shielding_materials, material_options):
    st.subheader("添加新的复合材料电磁屏蔽设计")

    test_id = st.text_input("试验件编号*", key="add_test_id")
    structure_type = st.selectbox("结构类型*", options=structure_types)

    st.subheader("铺层参数设置")
    layer_count = st.number_input("铺层层数*", min_value=1, value=1, step=1)
    layers = []
    for i in range(layer_count):
        cols = st.columns([3, 1, 1])
        with cols[0]:
            mat = st.selectbox(f"第{i + 1}层 材料", list(material_options.keys()), key=f"mat_{i}")
        with cols[1]:
            thk = st.number_input(
                f"厚度(mm)",
                min_value=0.00001,
                max_value=None,
                value=0.10,
                step=0.01,
                key=f"thk_{i}"
            )
        with cols[2]:
            ang = st.number_input(f"角度(°)", min_value=-90, max_value=90, value=0, step=5, key=f"ang_{i}")
        layers.append(f"第{i + 1}层: {mat}, 厚度: {thk}mm, 角度: {ang}°")

    thickness_summary = st.text_input("厚度汇总描述*")
    shielding_material = st.selectbox("屏蔽防护材料*", options=shielding_materials)

    st.markdown("---")
    st.subheader("试验件图片上传")
    if 'add_img_count' not in st.session_state:
        st.session_state['add_img_count'] = 1

    uploaded_images = []
    for i in range(st.session_state['add_img_count']):
        c1, c2 = st.columns([1, 2])
        with c1:
            img_file = st.file_uploader(f"图片 {i + 1}", type=["jpg", "png", "jpeg"], key=f"img_f_{i}")
        with c2:
            img_name = st.text_input(f"图片 {i + 1} 描述", key=f"img_n_{i}")
        uploaded_images.append((img_file, img_name))

    c_add, c_rm = st.columns([1, 10])
    with c_add:
        if st.button("➕增加图片"): st.session_state['add_img_count'] += 1; st.rerun()
    with c_rm:
        if st.session_state['add_img_count'] > 1 and st.button("➖移除图片"):
            st.session_state['add_img_count'] -= 1;
            st.rerun()

    st.markdown("---")
    st.subheader("12组测试/计算数据上传 (.dat)")
    st.info("文件数据格式：两列，第一列频率，第二列数值。请为其指定频率单位（默认GHz）")

    dat_uploads = {}
    dat_units = {}
    tab_calc, tab_test = st.tabs(["💻 计算数据", "🔬 测试数据"])

    def render_dat_uploaders(source_name, tab):
        with tab:
            c_hh, c_vv = st.columns(2)
            for config in DAT_CONFIGS:
                src, pol, dtype = config
                if src != source_name: continue

                target_col = c_hh if "HH" in pol else c_vv
                with target_col:
                    st.markdown(f"**{pol} - {dtype}**")
                    cc1, cc2 = st.columns([3, 1])
                    with cc1:
                        file_key = f"{src}_{pol}_{dtype}"
                        dat_uploads[config] = st.file_uploader("上传文件", type=['dat', 'txt'], key=file_key,
                                                               label_visibility="collapsed")
                    with cc2:
                        unit_key = f"unit_{src}_{pol}_{dtype}"
                        dat_units[config] = st.selectbox("单位", ["GHz", "MHz", "Hz"], index=0, key=unit_key,
                                                         label_visibility="collapsed")

    render_dat_uploaders("计算", tab_calc)
    render_dat_uploaders("测试", tab_test)

    if st.button("🚀 提交全部数据", type="primary"):
        if not test_id or not thickness_summary:
            st.error("试验件编号和厚度汇总为必填项！")
            return

        conn = create_connection()
        c = conn.cursor()
        try:
            now = datetime.now()
            layer_details_str = "\n".join(layers)
            c.execute("""INSERT INTO shielding_designs 
                         (test_id, structure_type, thickness_summary, layer_details, shielding_material, create_time, update_time)
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                      (test_id, structure_type, thickness_summary, layer_details_str, shielding_material, now, now))

            for f, n in uploaded_images:
                if f:
                    c.execute("INSERT INTO design_images (test_id, image_name, image_data) VALUES (?, ?, ?)",
                              (test_id, n if n else f.name, f.read()))

            for config, file_obj in dat_uploads.items():
                if file_obj:
                    src, pol, dtype = config
                    unit = dat_units[config]
                    c.execute("""INSERT INTO design_dat_files 
                                 (test_id, data_source, polarization, data_type, freq_unit, file_name, file_data)
                                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
                              (test_id, src, pol, dtype, unit, file_obj.name, file_obj.read()))

            conn.commit()
            clear_query_cache()  # 清理查询缓存
            st.success("🎉 数据全部入库成功！界面即将重置...")
            time.sleep(1.5)
            st.rerun()  # 强制刷新清空残留状态
        except sqlite3.IntegrityError:
            st.error("试验件编号已存在！")
        except Exception as e:
            conn.rollback()
            st.error(f"发生错误: {e}")
        finally:
            conn.close()


def update_design_page(structure_types, shielding_materials, material_options):
    st.subheader("修改复合材料电磁屏蔽设计")

    designs = get_shielding_designs()
    if not designs:
        st.warning("没有可修改的设计数据")
        return

    design_options = {d[0]: d for d in designs}
    selected_test_id = st.selectbox("选择要修改的试验件编号", list(design_options.keys()))

    if selected_test_id:
        design = design_options[selected_test_id]
        conn = create_connection()

        st.markdown("#### 1. 基础信息")
        new_structure_type = st.selectbox("结构类型*", options=structure_types,
                                          index=structure_types.index(design[1]) if design[1] in structure_types else 0)
        new_thickness = st.text_input("厚度汇总描述*", value=design[2])
        new_shielding_mat = st.selectbox("屏蔽防护材料*", options=shielding_materials,
                                         index=shielding_materials.index(design[4]) if design[
                                                                                           4] in shielding_materials else 0)

        new_layer_details = st.text_area("铺层详情 (每层一行)", value=design[3], height=150)

        st.markdown("#### 2. 试验件视图")
        imgs_df = pd.read_sql_query("SELECT img_id, image_name FROM design_images WHERE test_id=?", conn,
                                    params=(selected_test_id,))

        images_to_delete = []
        if not imgs_df.empty:
            st.write("已上传的图片 (勾选可删除):")
            for _, row in imgs_df.iterrows():
                if st.checkbox(f"删除: {row['image_name']}", key=f"del_img_{row['img_id']}"):
                    images_to_delete.append(row['img_id'])

        st.write("追加新图片:")
        if 'update_img_count' not in st.session_state:
            st.session_state['update_img_count'] = 1

        new_uploaded_images = []
        for i in range(st.session_state['update_img_count']):
            c1, c2 = st.columns([1, 2])
            with c1:
                img_file = st.file_uploader(f"新图片 {i + 1}", type=["jpg", "png", "jpeg"], key=f"upd_img_f_{i}")
            with c2:
                img_name = st.text_input(f"新图片 {i + 1} 描述", key=f"upd_img_n_{i}")
            new_uploaded_images.append((img_file, img_name))

        if st.button("➕ 增加图片上传位"): st.session_state['update_img_count'] += 1; st.rerun()

        st.markdown("#### 3. 补充/覆盖/删除测试计算数据 (.dat)")
        existing_dats = pd.read_sql_query(
            "SELECT data_source, polarization, data_type, freq_unit, file_name FROM design_dat_files WHERE test_id=?",
            conn, params=(selected_test_id,))

        existing_dat_dict = {}
        for _, r in existing_dats.iterrows():
            existing_dat_dict[(r['data_source'], r['polarization'], r['data_type'])] = r['freq_unit']

        update_dat_uploads = {}
        update_dat_units = {}
        update_dat_deletes = {}
        tab_calc, tab_test = st.tabs(["💻 计算数据", "🔬 测试数据"])

        def render_update_uploaders(source_name, tab):
            with tab:
                c_hh, c_vv = st.columns(2)
                for config in DAT_CONFIGS:
                    src, pol, dtype = config
                    if src != source_name: continue

                    target_col = c_hh if "HH" in pol else c_vv
                    with target_col:
                        has_data = config in existing_dat_dict
                        status_str = "✅ 已上传" if has_data else "❌ 未上传"

                        default_unit = existing_dat_dict.get(config, "GHz")
                        unit_idx = ["GHz", "MHz", "Hz"].index(default_unit) if default_unit in ["GHz", "MHz",
                                                                                                "Hz"] else 0

                        st.caption(f"{pol} - {dtype} ({status_str})")

                        if has_data:
                            del_key = f"del_dat_{src}_{pol}_{dtype}"
                            update_dat_deletes[config] = st.checkbox("🗑️ 删除此文件", key=del_key)

                        cc1, cc2 = st.columns([3, 1])
                        with cc1:
                            file_key = f"upd_{src}_{pol}_{dtype}"
                            update_dat_uploads[config] = st.file_uploader(f"覆盖/补充", type=['dat', 'txt'], key=file_key,
                                                                          label_visibility="collapsed")
                        with cc2:
                            unit_key = f"upd_unit_{src}_{pol}_{dtype}"
                            update_dat_units[config] = st.selectbox("单位", ["GHz", "MHz", "Hz"], index=unit_idx,
                                                                    key=unit_key, label_visibility="collapsed")

        render_update_uploaders("计算", tab_calc)
        render_update_uploaders("测试", tab_test)

        if st.button("💾 保存所有修改", type="primary"):
            c = conn.cursor()
            now = datetime.now()

            try:
                c.execute("""UPDATE shielding_designs 
                                     SET structure_type=?, thickness_summary=?, layer_details=?, shielding_material=?, update_time=?
                                     WHERE test_id=?""",
                          (new_structure_type, new_thickness, new_layer_details, new_shielding_mat, now,
                           selected_test_id))

                for img_id in images_to_delete:
                    c.execute("DELETE FROM design_images WHERE img_id=?", (img_id,))

                for f, n in new_uploaded_images:
                    if f:
                        c.execute("INSERT INTO design_images (test_id, image_name, image_data) VALUES (?, ?, ?)",
                                  (selected_test_id, n if n else f.name, f.read()))

                for config in DAT_CONFIGS:
                    src, pol, dtype = config
                    file_obj = update_dat_uploads.get(config)
                    unit = update_dat_units.get(config)

                    # 修复更新与删除冲突逻辑
                    if file_obj:
                        c.execute(
                            "DELETE FROM design_dat_files WHERE test_id=? AND data_source=? AND polarization=? AND data_type=?",
                            (selected_test_id, src, pol, dtype))
                        c.execute("""INSERT INTO design_dat_files 
                                             (test_id, data_source, polarization, data_type, freq_unit, file_name, file_data)
                                             VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                  (selected_test_id, src, pol, dtype, unit, file_obj.name, file_obj.read()))
                    elif update_dat_deletes.get(config, False):
                        c.execute(
                            "DELETE FROM design_dat_files WHERE test_id=? AND data_source=? AND polarization=? AND data_type=?",
                            (selected_test_id, src, pol, dtype))
                    else:
                        if config in existing_dat_dict and existing_dat_dict[config] != unit:
                            c.execute("""UPDATE design_dat_files SET freq_unit=? 
                                                 WHERE test_id=? AND data_source=? AND polarization=? AND data_type=?""",
                                      (unit, selected_test_id, src, pol, dtype))

                conn.commit()
                clear_query_cache()  # 清理查询缓存
                st.success("修改保存成功！")
            except Exception as e:
                conn.rollback()
                st.error(f"保存失败: {e}")
            finally:
                conn.close()
        else:
            conn.close()


def delete_design_page(structure_types, shielding_materials):
    st.subheader("批量删除复合材料电磁屏蔽设计")

    with st.form("delete_search_form"):
        c1, c2 = st.columns(2)
        with c1:
            s_type = st.selectbox("结构形式", [""] + structure_types)
        with c2:
            s_mat = st.selectbox("屏蔽防护材料", [""] + shielding_materials)
        submitted = st.form_submit_button("查询")

    if submitted or 'delete_search_results' in st.session_state:
        if submitted:
            designs = get_shielding_designs(structure_type=s_type if s_type else None,
                                            shielding_material=s_mat if s_mat else None)
            st.session_state['delete_search_results'] = designs
        else:
            designs = st.session_state['delete_search_results']

        if not designs:
            st.warning("未找到匹配的设计数据")
            return

        df = pd.DataFrame(designs, columns=['试验件编号', '结构', '厚度', '铺层', '屏蔽材料', '创建时间', '更新时间'])
        df.insert(0, '选择删除', False)

        st.markdown("### 勾选需要删除的记录")

        edited_df = st.data_editor(
            df[['选择删除', '试验件编号', '结构', '厚度', '屏蔽材料', '创建时间']],
            hide_index=True,
            column_config={
                "选择删除": st.column_config.CheckboxColumn("🗑️ 选择删除", default=False)
            },
            disabled=['试验件编号', '结构', '厚度', '屏蔽材料', '创建时间'],
            use_container_width=True,
            key="delete_data_editor"
        )

        selected_ids = edited_df[edited_df['选择删除']]['试验件编号'].tolist()

        if selected_ids:
            st.warning(f"⚠️ 已选择 {len(selected_ids)} 条记录。注意：删除后关联的图片和测试数据文件将被级联清空，无法恢复！")
            if st.button("确认批量删除", type="primary"):
                conn = create_connection()
                c = conn.cursor()
                try:
                    c.executemany("DELETE FROM shielding_designs WHERE test_id=?", [(tid,) for tid in selected_ids])
                    conn.commit()
                    clear_query_cache()  # 清理查询缓存
                    st.success(f"✅ 成功删除试验件：{', '.join(selected_ids)}")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"删除失败: {e}")
                finally:
                    conn.close()


def query_design_page(structure_types, materials, shielding_materials):
    st.subheader("查询与分析复合材料电磁屏蔽数据")

    with st.form("search_form"):
        c1, c2 = st.columns(2)
        with c1:
            s_type = st.selectbox("结构形式", [""] + structure_types)
        with c2:
            s_mat = st.selectbox("屏蔽防护材料", [""] + shielding_materials)
        submitted = st.form_submit_button("查询")

    if submitted or 'search_results' in st.session_state:
        if submitted:
            designs = get_shielding_designs(structure_type=s_type if s_type else None,
                                            shielding_material=s_mat if s_mat else None)
            st.session_state['search_results'] = designs
        else:
            designs = st.session_state['search_results']

        if not designs:
            st.warning("未找到匹配数据")
            return

        df = pd.DataFrame(designs, columns=['试验件编号', '结构', '厚度', '铺层', '屏蔽材料', '创建时间', '更新时间'])
        st.dataframe(df[['试验件编号', '结构', '厚度', '屏蔽材料']])

        selected_tid = st.selectbox("选择试验件查看详情与对比分析", df['试验件编号'].tolist())

        conn = create_connection()
        details = df[df['试验件编号'] == selected_tid].iloc[0]

        with st.expander(f"📖 基础信息 - {selected_tid}", expanded=True):
            st.text(details['铺层'])

            imgs = pd.read_sql_query("SELECT image_name, image_data FROM design_images WHERE test_id=?", conn,
                                     params=(selected_tid,))
            if not imgs.empty:
                st.markdown("**试验件视图**")
                img_cols = st.columns(min(len(imgs), 3))
                for idx, row in imgs.iterrows():
                    with img_cols[idx % 3]:
                        image = Image.open(io.BytesIO(row['image_data']))
                        st.image(image, caption=row['image_name'], use_container_width=True)

        st.markdown("### 📈 数据交叉对比分析")
        dat_files = pd.read_sql_query(
            "SELECT data_source, polarization, data_type, freq_unit, file_name, file_data FROM design_dat_files WHERE test_id=?",
            conn, params=(selected_tid,))
        conn.close()

        if dat_files.empty:
            st.warning("该试验件暂未上传任何数据文件。")
        else:
            dat_files['plot_label'] = dat_files['data_source'] + " - " + dat_files['polarization'] + " - " + dat_files[
                'data_type']
            options = dat_files['plot_label'].tolist()

            selected_plots = st.multiselect("选择要绘制并在同一坐标系内对比的数据曲线：", options,
                                            default=options[:2] if len(options) >= 2 else options)

            normalize_y = st.checkbox("启用 Y 轴数据归一化 (适用于对比介电常数与屏蔽效能等不同量级数据)", value=False)

            # 修复空ZIP包隐患：将图表渲染和下载按钮统统移入 if 语句内
            if selected_plots:
                fig, ax = plt.subplots(figsize=(10, 6))

                for sp in selected_plots:
                    row = dat_files[dat_files['plot_label'] == sp].iloc[0]
                    try:
                        curve_df = pd.read_csv(io.BytesIO(row['file_data']), sep=r'\s+', header=None,
                                               names=["Freq", "Value"], comment='#')
                        curve_df['Freq'] = pd.to_numeric(curve_df['Freq'], errors='coerce')
                        curve_df['Value'] = pd.to_numeric(curve_df['Value'], errors='coerce')
                        curve_df = curve_df.dropna()

                        freq_data = curve_df['Freq']
                        if row['freq_unit'] == 'MHz':
                            freq_data = freq_data / 1000.0
                        elif row['freq_unit'] == 'Hz':
                            freq_data = freq_data / 1e9

                        y_data = curve_df['Value']
                        legend_label = f"{sp} (原始单位:{row['freq_unit']})"

                        if normalize_y and y_data.max() != 0:
                            y_data = y_data / y_data.abs().max()
                            legend_label += " [归一化]"

                        ax.plot(freq_data, y_data, label=legend_label, linewidth=1.5)

                    except Exception as e:
                        st.error(f"无法解析数据文件 {row['file_name']}: {str(e)}")

                ax.set_xlabel('统一频率 (GHz)')
                ylabel_text = '归一化数值' if normalize_y else '数值'
                ax.set_ylabel(ylabel_text)
                ax.set_title(f"{selected_tid} 性能数据对比")
                ax.grid(True, linestyle='--', alpha=0.6)
                ax.legend()

                st.pyplot(fig)
                plt.close(fig)

                st.markdown("**批量打包下载数据**")
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for sp in selected_plots:
                        row = dat_files[dat_files['plot_label'] == sp].iloc[0]

                        ext = os.path.splitext(row['file_name'])[1]
                        if not ext: ext = ".dat"
                        clean_pol = row['polarization'].replace('（', '(').replace('）', ')')
                        standard_filename = f"{selected_tid}_{row['data_source']}_{clean_pol}_{row['data_type']}{ext}"

                        zip_file.writestr(standard_filename, row['file_data'])

                zip_buffer.seek(0)
                st.download_button("📦 下载选中数据的ZIP包", data=zip_buffer, file_name=f"{selected_tid}_data.zip",
                                   mime="application/zip")


main()