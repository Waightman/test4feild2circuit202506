import streamlit as st
import pandas as pd
import numpy as np
import os
# 保持你原来的引用，假设这些库在你的环境中可用
from vectfit3 import vectfit
from vectfit3 import opts
from scipy.constants import pi
import vectorfit_wyz as rf
# import skrf as rf
import matplotlib.pyplot as plt
import wyz_io

# ### 修改点 1: 初始化 session_state
# 用于存储上传控件的ID、计算后的SPICE内容、计算后的图片
if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = 0
if 'result_spice' not in st.session_state:
    st.session_state['result_spice'] = ""
if 'result_fig' not in st.session_state:
    st.session_state['result_fig'] = None
if 'result_from_tab' not in st.session_state:
    st.session_state['result_from_tab'] = None  # 记录是哪个tab产生的结果


# 定义一个函数来清理并转换为复数
def to_complex(val):
    try:
        val = val.replace('i', 'j')  # 替换 'i' 为 'j'
        return complex(val)  # 转换为复数
    except ValueError:
        print(f"无法转换为复数: {val}")
        return np.nan


# 函数用于验证路径的合法性
def is_valid_path(path):
    return os.path.isdir(path) or os.path.isfile(path)


#########0  显示公司logo
LOGO_PATH = "company_logo.jpg"
if not os.path.exists(LOGO_PATH):
    # st.error("公司logo图片未找到，请确保company_logo.jpg文件存在") # 为避免干扰演示，这里建议注释掉或保留原样
    logo_html = ""
else:
    logo_base64 = wyz_io.image_to_base64(LOGO_PATH)
    logo_html = f"""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="data:image/jpeg;base64,{logo_base64}" alt="公司标徽" style="height: 60px;">
        <h3 style="margin: 0; font-size: 42px;">中航通飞华南飞机工业有限公司</h3>
    </div>
    """
    st.markdown(logo_html, unsafe_allow_html=True)

# 设置网页标题
st.title('电磁环境效应仿真支持平台V1.0')
st.header('1. 场路转化说明')
st.text('本仿真平台支持将电磁场仿真得到的电磁数据利用矢量拟合等方法转化为时域电路模型，'
        '文件默认类型为ztm文件，每个文件对应一个频点的数据,仿真中单位默认为MHz,至少上传3个频点的数据')

### 场路转化模块
is_data_ready = 0
uploaded_file_set = []

# ### 修改点 2: 给 file_uploader 绑定动态 key
# key 的值由 session_state['uploader_key'] 控制，数值变了，组件就会重置
uploaded_file_set = st.file_uploader(
    "选择文件:",
    type=["txt", "ztm", "sparameters"],
    accept_multiple_files=True,
    key=f"file_uploader_{st.session_state['uploader_key']}"
)

spice_model_path = st.text_input('请输入spice模型文件存储路径（可以不设置，默认为当前工程目录）', max_chars=100, help='最大长度为100字符')

if spice_model_path:
    if not is_valid_path(spice_model_path):
        st.error(f"路径 '{spice_model_path}' 不合法！请确保路径存在且是文件夹或文件。")
    else:
        st.success(f"路径 '{spice_model_path}' 合法！")

Z_f_n_n_list = []
fre_list = []

# 数据处理逻辑保持不变
if len(uploaded_file_set) > 3:
    for uploaded_file in uploaded_file_set:
        # st.write(uploaded_file.name) # 稍微减少刷屏，可保留
        file_name, file_extension = os.path.splitext(uploaded_file.name)
        match file_extension:
            case ".txt":
                dataframe = pd.read_csv(uploaded_file, delimiter=',', header=None)
                df_complex = dataframe.applymap(to_complex)
                arr = df_complex.to_numpy()
                opts["asymp"] = 3
                opts["phaseplot"] = True
                N = arr.shape[1]
                weights = np.ones(N, dtype=np.float64)
                n = 3
                poles = -2 * pi * np.logspace(0, 4, n, dtype=np.complex128)
                arr = np.transpose(arr)
                s = arr[:, 0]
                f = arr[:, 1]
                (SER, poles, rmserr, fit) = vectfit(f, s, poles, weights, opts)
            case ".ztm":
                ztm_file = uploaded_file
                result_data, fre_data = wyz_io.read_matrix_from_txt(ztm_file)
                Z_f_n_n_list.append(result_data)
                fre_list.append(fre_data)
                inut_file_type = 1
            case ".sparameters":
                ztm_file = uploaded_file
                result_data, fre_data = wyz_io.read_matrix_from_txt2(ztm_file)
                Z_f_n_n_list.append(result_data)
                fre_list.append(fre_data)
                inut_file_type = 2
            case _:
                print("文件格式错误")

    frequency_ordered_index = np.argsort(fre_list)
    Z_f_n_n_list_ordered = []
    frequency_ordered = []
    for fer_ordered in frequency_ordered_index:
        Z_f_n_n_list_ordered.append(Z_f_n_n_list[fer_ordered])
        frequency_ordered.append(fre_list[fer_ordered])
    Z_fnn_matrix = np.stack(Z_f_n_n_list_ordered, axis=0)
    is_data_ready = 1
else:
    # 只有当没有历史结果显示时，才提示文件太少，避免清空后看着难受
    if not st.session_state['result_spice']:
        st.text("文件数量太少,请重新输入")
    is_data_ready = 0

st.title("场路转换模式选择")
tab1, tab2 = st.tabs(["自动模式", "手动模式"])

# 自动模式
with tab1:
    st.header("自动模式参数设置")
    # 参数输入保持不变...
    col1, col2, col3 = st.columns(3)
    with col1:
        n_poles_init_real = st.number_input("初始实数极点数量", min_value=1, value=3, step=1, key="auto_n_poles_init_real")
        n_poles_init_cmplx = st.number_input("初始复数极点数量", min_value=1, value=3, step=1, key="auto_n_poles_init_cmplx")
        n_poles_add = st.number_input("每次增加的极点数量", min_value=1, value=3, step=1, key="auto_n_poles_add")
    with col2:
        model_order_max = st.number_input("最大模型阶数", min_value=1, value=100, step=1, key="auto_model_order_max")
        iters_start = st.number_input("初始拟合迭代次数", min_value=1, value=3, step=1, key="auto_iters_start")
        iters_inter = st.number_input("中间拟合迭代次数", min_value=1, value=3, step=1, key="auto_iters_inter")
    with col3:
        iters_final = st.number_input("最终拟合迭代次数", min_value=1, value=5, step=1, key="auto_iters_final")
        target_error = st.number_input("目标误差", min_value=0.0, value=1e-2, format="%.5f", key="auto_target_error")
        alpha = st.number_input("正则化参数 alpha", min_value=0.0, value=0.03, format="%.3f", key="auto_alpha")

    with st.expander("高级参数设置"):
        gamma = st.number_input("正则化参数 gamma", min_value=0.0, value=0.03, format="%.3f", key="auto_gamma")
        nu_samples = st.number_input("采样密度", min_value=0.0, value=1.0, format="%.1f", key="auto_nu_samples")
        parameter_type = st.selectbox("参数类型", options=['s'], index=0, key="auto_parameter_type")
        compare_flag_on = st.toggle("启用结果自动比较功能（S11）", value=True)

    # ### 修改点 3: 按钮逻辑修改
    if st.button("开始自动转换"):
        if is_data_ready == 0:
            st.error("请先上传足够的阻抗数据文件！")
        else:
            with st.spinner("正在计算中..."):
                if inut_file_type == 1:
                    ntw = rf.Network(frequency=np.array(frequency_ordered) * 1e6, z=Z_fnn_matrix)
                else:
                    ntw = rf.Network(frequency=np.array(frequency_ordered) * 1e6, s=Z_fnn_matrix)

                vf = rf.VectorFitting(ntw)
                vf.auto_fit(n_poles_init_real=n_poles_init_real,
                            n_poles_init_cmplx=n_poles_init_cmplx,
                            n_poles_add=n_poles_add,
                            model_order_max=model_order_max,
                            iters_start=iters_start,
                            iters_inter=iters_inter,
                            iters_final=iters_final,
                            target_error=target_error,
                            alpha=alpha,
                            gamma=gamma,
                            nu_samples=nu_samples,
                            parameter_type=parameter_type)

                # 生成 SPICE 内容
                vf.write_spice_subcircuit_s('wyz2.sp')
                temp_spice_content = vf.generate_spice_subcircuit_s2()

                # 保存内容到 session_state
                st.session_state['result_spice'] = temp_spice_content
                st.session_state['result_from_tab'] = 'auto'

                # 处理图片
                if compare_flag_on:
                    frequecy_fit = np.linspace(0, frequency_ordered[-1] * 1e6, len(frequency_ordered) * 10)
                    fit_data = vf.get_model_response(0, 0, frequecy_fit)
                    Zij = fit_data

                    fig, ax = plt.subplots()
                    ax.plot(frequecy_fit / 1e6, np.abs(Zij), label='Fitted Model')
                    s11 = ntw.s[:, 0, 0]
                    ax.plot(frequency_ordered, np.abs(s11), 'o', label='Original Data')
                    ax.set_xlabel('Frequency (MHz)')
                    ax.set_ylabel('Magnitude')
                    ax.set_title('Model Response')
                    ax.legend()
                    ax.grid(True)

                    # 保存 Figure 对象到 session_state
                    st.session_state['result_fig'] = fig
                else:
                    st.session_state['result_fig'] = None

                # ### 核心修改：更新 Key 并重跑页面（实现自动清空）
                st.session_state['uploader_key'] += 1
                st.rerun()

    # ### 修改点 4: 结果展示逻辑（放在按钮外面）
    # 页面刷新后，文件没了，但 session_state 还有结果，在这里显示
    if st.session_state['result_spice'] and st.session_state['result_from_tab'] == 'auto':
        st.success("转换成功！上传文件已重置。")

        # 显示图片
        if st.session_state['result_fig']:
            st.pyplot(st.session_state['result_fig'])

        # 显示下载和存储
        spice_content_str = st.session_state['result_spice']
        storage_option = st.radio("选择存储方式：", options=["下载到当前电脑", "存储到服务器本地"], index=0, key="auto_storage_res")

        if storage_option == "下载到当前电脑":
            st.download_button(
                label="下载 SPICE 文件",
                data=spice_content_str,
                file_name="example.cir",
                mime="text/plain"
            )
        else:
            default_path = os.path.join(os.getcwd(), "example.cir")
            file_path = st.text_input("输入服务器本地存储路径：", value=default_path, key="auto_path_res")
            if st.button("存储到服务器本地", key="auto_save_btn"):
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "w") as f:
                        f.write(spice_content_str)
                    st.success(f"文件已成功存储到：{os.path.abspath(file_path)}")
                except Exception as e:
                    st.error(f"存储文件时出错：{e}")

        # 提供一个清除结果的按钮（可选）
        if st.button("清除结果", key="auto_clear_res"):
            st.session_state['result_spice'] = ""
            st.session_state['result_fig'] = None
            st.rerun()

# 手动模式
with tab2:
    st.header("手动模式参数设置")
    # 参数输入保持不变...
    col1, col2 = st.columns(2)
    with col1:
        n_poles_real = st.number_input("实数极点数量", min_value=1, value=2, step=1, key="manual_n_poles_real")
        n_poles_cmplx = st.number_input("复数极点数量", min_value=1, value=2, step=1, key="manual_n_poles_cmplx")
        init_pole_spacing = st.selectbox("初始极点间距", options=['lin', 'log'], index=0, key="manual_init_pole_spacing")
    with col2:
        parameter_type = st.selectbox("参数类型", options=['s', 'z'], index=0, key="manual_parameter_type")
        fit_constant = st.checkbox("拟合常数项", value=True, key="manual_fit_constant")
        fit_proportional = st.checkbox("拟合比例项", value=False, key="manual_fit_proportional")

    if st.button("开始手动拟合"):
        if is_data_ready == 0:
            st.error("请先上传足够的阻抗数据文件！")
        else:
            ntw = rf.Network(frequency=np.array(frequency_ordered) * 1e6, z=Z_fnn_matrix)
            vf = rf.VectorFitting(ntw)
            vf.vector_fit(n_poles_real=n_poles_real, n_poles_cmplx=n_poles_cmplx,
                          init_pole_spacing=init_pole_spacing,
                          parameter_type=parameter_type,
                          fit_constant=fit_constant,
                          fit_proportional=fit_proportional)

            frequecy_fit = np.linspace(0, 10e3, 21)  # 注意：这里你的原代码范围可能需要根据实际数据调整
            vf.write_spice_subcircuit_s('wyz2.cir')
            temp_spice_content = vf.generate_spice_subcircuit_s2()

            # 保存到 Session State
            st.session_state['result_spice'] = temp_spice_content
            st.session_state['result_from_tab'] = 'manual'
            st.session_state['result_fig'] = None  # 手动模式原代码未画图，置空

            # 清空上传并刷新
            st.session_state['uploader_key'] += 1
            st.rerun()

    # 手动模式的结果展示
    if st.session_state['result_spice'] and st.session_state['result_from_tab'] == 'manual':
        st.success("手动拟合转换成功！上传文件已重置。")
        spice_content_str = st.session_state['result_spice']

        storage_option = st.radio("选择存储方式：", options=["下载到当前电脑", "存储到服务器本地"], index=0, key="manual_storage_res")

        if storage_option == "下载到当前电脑":
            st.download_button(
                label="下载 SPICE 文件",
                data=spice_content_str,
                file_name="example.cir",
                mime="text/plain"
            )
        else:
            default_path = os.path.join(os.getcwd(), "example.cir")
            file_path = st.text_input("输入服务器本地存储路径：", value=default_path, key="manual_path_res")
            if st.button("存储到服务器本地", key="manual_save_btn"):
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "w") as f:
                        f.write(spice_content_str)
                    st.success(f"文件已成功存储到：{os.path.abspath(file_path)}")
                except Exception as e:
                    st.error(f"存储文件时出错：{e}")

        if st.button("清除结果", key="manual_clear_res"):
            st.session_state['result_spice'] = ""
            st.rerun()