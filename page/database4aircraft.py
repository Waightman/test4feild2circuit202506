import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import os
#from io import StringIO
from io import BytesIO, StringIO  # 添加这行
# 初始化数据库
def init_db():
    # 连接到当前目录下的    shielding_design.db    数据库文件。
    # 如果文件不存在，会自动创建；如果已存在，则直接打开。
    conn = sqlite3.connect('shielding_design.db')
    c = conn.cursor()
    # 创建基体材料表，执行SQL语句
    c.execute('''CREATE TABLE IF NOT EXISTS materials
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  model TEXT,
                  supplier TEXT,
                  standard TEXT)''')

    # 创建屏蔽设计表
    c.execute('''CREATE TABLE IF NOT EXISTS shielding_designs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  test_id TEXT UNIQUE,
                  base_material_id INTEGER,
                  structure_type TEXT,
                  thickness TEXT,
                  shielding_material TEXT,
                  shielding_data TEXT,
                  dielectric_data TEXT,
                  FOREIGN KEY(base_material_id) REFERENCES materials(id))''')
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

    # 检查是否已插入数据
    c.execute("SELECT COUNT(*) FROM materials")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO materials (name, model, supplier, standard) VALUES (?, ?, ?, ?)", materials_data)

    conn.commit()
    conn.close()


# 初始化数据库
init_db()
# 获取所有基体材料
def get_materials():
    conn = sqlite3.connect('shielding_design.db')
    c = conn.cursor()
    c.execute("SELECT id, name, model, supplier, standard FROM materials")
    materials = c.fetchall()
    conn.close()
    return materials


# 添加新的屏蔽设计
def add_shielding_design(test_id, base_material_id, structure_type, thickness, shielding_material, shielding_data,
                         dielectric_data):
    conn = sqlite3.connect('shielding_design.db')
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO shielding_designs (test_id, base_material_id, structure_type, thickness, shielding_material, shielding_data, dielectric_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (test_id, base_material_id, structure_type, thickness, shielding_material, shielding_data, dielectric_data))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# 更新屏蔽设计
def update_shielding_design(test_id, base_material_id, structure_type, thickness, shielding_material, shielding_data,
                            dielectric_data):
    conn = sqlite3.connect('shielding_design.db')
    c = conn.cursor()
    c.execute(
        "UPDATE shielding_designs SET base_material_id=?, structure_type=?, thickness=?, shielding_material=?, shielding_data=?, dielectric_data=? WHERE test_id=?",
        (base_material_id, structure_type, thickness, shielding_material, shielding_data, dielectric_data, test_id))
    conn.commit()
    conn.close()


# 删除屏蔽设计
def delete_shielding_design(test_id):
    conn = sqlite3.connect('shielding_design.db')
    c = conn.cursor()
    c.execute("DELETE FROM shielding_designs WHERE test_id=?", (test_id,))
    conn.commit()
    conn.close()


# 查询屏蔽设计
def get_shielding_designs(base_material=None, structure_type=None, thickness=None, shielding_material=None):
    conn = sqlite3.connect('shielding_design.db')
    c = conn.cursor()

    query = """SELECT s.test_id, m.name, m.model, m.supplier, m.standard, 
                      s.structure_type, s.thickness, s.shielding_material,
                      s.shielding_data, s.dielectric_data
               FROM shielding_designs s
               JOIN materials m ON s.base_material_id = m.id
               WHERE 1=1"""

    params = []

    if base_material:
        query += " AND m.name = ?"
        params.append(base_material)

    if structure_type:
        query += " AND s.structure_type = ?"
        params.append(structure_type)

    if thickness:
        query += " AND s.thickness LIKE ?"
        params.append(f"%{thickness}%")

    if shielding_material:
        query += " AND s.shielding_material = ?"
        params.append(shielding_material)

    c.execute(query, params)
    designs = c.fetchall()
    conn.close()
    return designs


# 获取单个屏蔽设计
def get_shielding_design(test_id):
    conn = sqlite3.connect('shielding_design.db')
    c = conn.cursor()
    c.execute("""SELECT s.test_id, m.id, m.name, m.model, m.supplier, m.standard, 
                        s.structure_type, s.thickness, s.shielding_material,
                        s.shielding_data, s.dielectric_data
                 FROM shielding_designs s
                 JOIN materials m ON s.base_material_id = m.id
                 WHERE s.test_id = ?""", (test_id,))
    design = c.fetchone()
    conn.close()
    return design


# 主页面
def main():
    st.title("复合材料飞机结构电磁屏蔽设计数据库系统")

    # # 侧边栏导航
    # menu = ["添加新设计", "修改设计", "删除设计", "查询设计"]
    # choice = st.sidebar.selectbox("菜单", menu)

    # 侧边栏导航
    st.sidebar.title("导航")
    choice = st.sidebar.radio(
        "选择操作类型",
        ("添加新设计", "修改设计", "删除设计", "查询设计")
    )


    # 获取所有基体材料
    materials = get_materials()
    material_options = {f"{m[1]} ({m[2]})": m[0] for m in materials}

    # 结构形式选项
    structure_types = ["层压", "蜂窝夹层", "泡沫夹层"]

    # 屏蔽防护材料选项
    shielding_materials = ["铜网", "碳基膜"]

    if choice == "添加新设计":
        st.subheader("添加新的复合材料电磁屏蔽设计")

        with st.form("add_design_form"):
            test_id = st.text_input("试验件编号*", key="add_test_id")

            # 基体材料选择
            selected_material_name = st.selectbox(
                "复合材料的基体*",
                options=list(material_options.keys()),
                key="add_base_material"
            )
            base_material_id = material_options[selected_material_name]

            # 结构形式选择
            structure_type = st.selectbox(
                "结构形式*",
                options=structure_types,
                key="add_structure_type"
            )

            thickness = st.text_input("厚度（含铺层方式）*", key="add_thickness")

            # 屏蔽防护材料选择
            shielding_material = st.selectbox(
                "屏蔽防护材料*",
                options=shielding_materials,
                key="add_shielding_material"
            )

            # 屏蔽效能数据上传
            st.markdown("**复合材料在各频率下的屏蔽效能**")
            shielding_file = st.file_uploader(
                "上传屏蔽效能数据文件（txt格式，两列：频率、屏蔽效能）",
                type=["txt"],
                key="add_shielding_file"
            )

            # 介电常数数据上传
            st.markdown("**介电常数实部和虚部**")
            dielectric_file = st.file_uploader(
                "上传介电常数数据文件（txt格式，三列：频率、实部、虚部）",
                type=["txt"],
                key="add_dielectric_file"
            )

            submitted = st.form_submit_button("提交")

            if submitted:
                if not test_id:
                    st.error("试验件编号不能为空")
                elif not thickness:
                    st.error("厚度（含铺层方式）不能为空")
                elif not shielding_file or not dielectric_file:
                    st.error("请上传屏蔽效能和介电常数数据文件")
                else:
                    # 读取屏蔽效能数据
                    shielding_data = shielding_file.getvalue().decode("utf-8")

                    # 读取介电常数数据
                    dielectric_data = dielectric_file.getvalue().decode("utf-8")

                    # 添加到数据库
                    if add_shielding_design(test_id, base_material_id, structure_type, thickness,
                                            shielding_material, shielding_data, dielectric_data):
                        st.success("设计数据添加成功！")
                    else:
                        st.error("试验件编号已存在，请使用不同的编号")

    elif choice == "修改设计":
        st.subheader("修改复合材料电磁屏蔽设计")

        # 获取所有设计用于选择
        designs = get_shielding_designs()
        design_options = {d[0]: d for d in designs}

        if not design_options:
            st.warning("没有可修改的设计数据")
        else:
            selected_test_id = st.selectbox(
                "选择要修改的设计（试验件编号）",
                options=list(design_options.keys()),
                key="modify_select"
            )

            if selected_test_id:
                design = design_options[selected_test_id]

                with st.form("modify_design_form"):
                    st.text_input("试验件编号", value=design[0], disabled=True, key="modify_test_id")

                    # 基体材料选择
                    current_material = f"{design[1]} ({design[2]})"
                    selected_material_name = st.selectbox(
                        "复合材料的基体*",
                        options=list(material_options.keys()),
                        index=list(material_options.keys()).index(current_material),
                        key="modify_base_material"
                    )
                    base_material_id = material_options[selected_material_name]

                    # 结构形式选择
                    structure_type = st.selectbox(
                        "结构形式*",
                        options=structure_types,
                        index=structure_types.index(design[5]),
                        key="modify_structure_type"
                    )

                    thickness = st.text_input("厚度（含铺层方式）*", value=design[6], key="modify_thickness")

                    # 屏蔽防护材料选择
                    shielding_material = st.selectbox(
                        "屏蔽防护材料*",
                        options=shielding_materials,
                        index=shielding_materials.index(design[7]),
                        key="modify_shielding_material"
                    )

                    # 显示当前屏蔽效能数据
                    st.markdown("**当前屏蔽效能数据**")
                    shielding_df = pd.read_csv(StringIO(design[8]), sep="\s+", header=None, names=["频率", "屏蔽效能"])
                    st.dataframe(shielding_df)

                    # 屏蔽效能数据上传
                    st.markdown("**更新屏蔽效能数据**")
                    shielding_file = st.file_uploader(
                        "上传新的屏蔽效能数据文件（txt格式，两列：频率、屏蔽效能）",
                        type=["txt"],
                        key="modify_shielding_file"
                    )

                    # 显示当前介电常数数据
                    st.markdown("**当前介电常数数据**")
                    dielectric_df = pd.read_csv(StringIO(design[9]), sep="\s+", header=None, names=["频率", "实部", "虚部"])
                    st.dataframe(dielectric_df)

                    # 介电常数数据上传
                    st.markdown("**更新介电常数数据**")
                    dielectric_file = st.file_uploader(
                        "上传新的介电常数数据文件（txt格式，三列：频率、实部、虚部）",
                        type=["txt"],
                        key="modify_dielectric_file"
                    )

                    submitted = st.form_submit_button("更新")

                    if submitted:
                        if not thickness:
                            st.error("厚度（含铺层方式）不能为空")
                        else:
                            # 使用新数据或保留原数据
                            new_shielding_data = shielding_file.getvalue().decode("utf-8") if shielding_file else \
                            design[8]
                            new_dielectric_data = dielectric_file.getvalue().decode("utf-8") if dielectric_file else \
                            design[9]

                            # 更新数据库
                            update_shielding_design(selected_test_id, base_material_id, structure_type,
                                                    thickness, shielding_material, new_shielding_data,
                                                    new_dielectric_data)
                            st.success("设计数据更新成功！")

    elif choice == "删除设计":
        st.subheader("删除复合材料电磁屏蔽设计")

        # 获取所有设计用于选择
        designs = get_shielding_designs()
        design_options = {d[0]: d for d in designs}

        if not design_options:
            st.warning("没有可删除的设计数据")
        else:
            selected_test_id = st.selectbox(
                "选择要删除的设计（试验件编号）",
                options=list(design_options.keys()),
                key="delete_select"
            )

            if selected_test_id:
                design = design_options[selected_test_id]

                st.warning("以下设计将被删除，此操作不可恢复！")
                st.write(f"试验件编号: {design[0]}")
                st.write(f"基体材料: {design[1]} ({design[2]})")
                st.write(f"结构形式: {design[5]}")
                st.write(f"厚度: {design[6]}")
                st.write(f"屏蔽防护材料: {design[7]}")

                if st.button("确认删除"):
                    delete_shielding_design(selected_test_id)
                    st.success("设计数据已删除")

    elif choice == "查询设计":
        st.subheader("查询复合材料电磁屏蔽设计")

        with st.form("search_form"):
            col1, col2 = st.columns(2)

            with col1:
                # 基体材料筛选
                base_material_filter = st.selectbox(
                    "基体材料",
                    options=[""] + list(set([m[1] for m in materials])),
                    key="search_base_material"
                )

                # 结构形式筛选
                structure_type_filter = st.selectbox(
                    "结构形式",
                    options=[""] + structure_types,
                    key="search_structure_type"
                )

            with col2:
                # 厚度筛选
                thickness_filter = st.text_input(
                    "厚度（含铺层方式）",
                    key="search_thickness"
                )

                # 屏蔽防护材料筛选
                shielding_material_filter = st.selectbox(
                    "屏蔽防护材料",
                    options=[""] + shielding_materials,
                    key="search_shielding_material"
                )

            submitted = st.form_submit_button("查询")

        if submitted:
            # 执行查询
            designs = get_shielding_designs(
                base_material=base_material_filter if base_material_filter else None,
                structure_type=structure_type_filter if structure_type_filter else None,
                thickness=thickness_filter if thickness_filter else None,
                shielding_material=shielding_material_filter if shielding_material_filter else None
            )

            if not designs:
                st.warning("没有找到匹配的设计数据")
            else:
                st.success(f"找到 {len(designs)} 条匹配的设计数据")

                # 显示简要结果列表
                summary_data = []
                for design in designs:
                    summary_data.append({
                        "试验件编号": design[0],
                        "基体材料": f"{design[1]} ({design[2]})",
                        "供应商": design[3],
                        "标准": design[4],
                        "结构形式": design[5],
                        "厚度": design[6],
                        "屏蔽防护材料": design[7]
                    })
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(pd.DataFrame(summary_data))
####这里增加数据导出功能
                # 添加导出功能
                st.subheader("数据导出")

                # 创建Excel文件的字节流
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    # 导出摘要数据
                    summary_df.to_excel(writer, sheet_name='设计摘要', index=False)

                    # 为每个设计创建单独的工作表
                    for design in designs:
                        # 屏蔽效能数据
                        try:
                            shielding_df = pd.read_csv(StringIO(design[8]), sep="\s+", header=None,
                                                       names=["频率", "屏蔽效能"])
                            shielding_df.to_excel(writer, sheet_name=f"{design[0]}_屏蔽效能", index=False)
                        except:
                            pass

                        # 介电常数数据
                        try:
                            dielectric_df = pd.read_csv(StringIO(design[9]), sep="\s+", header=None,
                                                        names=["频率", "实部", "虚部"])
                            dielectric_df.to_excel(writer, sheet_name=f"{design[0]}_介电常数", index=False)
                        except:
                            pass

                # 准备下载按钮
                output.seek(0)
                st.download_button(
                    label="导出为Excel文件",
                    data=output,
                    file_name='屏蔽设计数据.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )

                # 使用expander来显示详细数据，而不是selectbox
                for design in designs:
                    with st.expander(f"详细数据 - {design[0]}"):
                        st.subheader("详细设计数据")
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write(f"**试验件编号**: {design[0]}")
                            st.write(f"**基体材料**: {design[1]}")
                            st.write(f"**牌号**: {design[2]}")
                            st.write(f"**供应商**: {design[3]}")
                            st.write(f"**标准**: {design[4]}")

                        with col2:
                            st.write(f"**结构形式**: {design[5]}")
                            st.write(f"**厚度（含铺层方式）**: {design[6]}")
                            st.write(f"**屏蔽防护材料**: {design[7]}")

                        # 显示屏蔽效能数据
                        st.subheader("屏蔽效能数据")
                        try:
                            shielding_df = pd.read_csv(StringIO(design[8]), sep="\s+", header=None,
                                                       names=["频率", "屏蔽效能"])
                            st.dataframe(shielding_df)
                            st.line_chart(shielding_df.set_index("频率"))
                        except Exception as e:
                            st.error(f"解析屏蔽效能数据失败: {str(e)}")

                        # 显示介电常数数据
                        st.subheader("介电常数数据")
                        try:
                            dielectric_df = pd.read_csv(StringIO(design[9]), sep="\s+", header=None,
                                                        names=["频率", "实部", "虚部"])
                            st.dataframe(dielectric_df)
                            col1, col2 = st.columns(2)
                            with col1:
                                st.line_chart(dielectric_df[["频率", "实部"]].set_index("频率"))
                            with col2:
                                st.line_chart(dielectric_df[["频率", "虚部"]].set_index("频率"))
                        except Exception as e:
                            st.error(f"解析介电常数数据失败: {str(e)}")


main()