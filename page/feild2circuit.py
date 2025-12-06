import streamlit as st
import pandas as pd
import numpy as np
import os
from vectfit3 import vectfit
from vectfit3 import opts
from scipy.constants import pi
import vectorfit_wyz as rf
#import skrf as rf
import matplotlib.pyplot as plt
import wyz_io

# 定义一个函数来清理并转换为复数
def to_complex(val):
    try:
        # 替换 'i' 为 'j'，然后转换为复数
        val = val.replace('i', 'j')  # 替换 'i' 为 'j'
        return complex(val)  # 转换为复数
    except ValueError:
        # 如果无法转换为复数，打印错误并返回 NaN
        print(f"无法转换为复数: {val}")
        return np.nan


# 函数用于验证路径的合法性
def is_valid_path(path):
    # 检查路径是否存在且为有效目录或文件
    return os.path.isdir(path) or os.path.isfile(path)
#########0  显示公司logo
LOGO_PATH = "company_logo.jpg"
# 检查图片是否存在
if not os.path.exists(LOGO_PATH):
    st.error("公司logo图片未找到，请确保company_logo.jpg文件存在")
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
# 展示一级标题
st.header('1. 场路转化说明')
st.text('本仿真平台支持将电磁场仿真得到的电磁数据利用矢量拟合等方法转化为时域电路模型，'
        '文件默认类型为ztm文件，每个文件对应一个频点的数据,仿真中单位默认为MHz,至少上传3个频点的数据')

### 场路转化模块
####1. 定义一个文件长传按钮，支持的类型暂定为txt，xls以及csv三种类型
is_data_ready = 0###定义一个标志状态，0表示阻抗数据没有准备好，1表示数据准备好，可以进行转换
uploaded_file_set=[]
uploaded_file_set = st.file_uploader("选择文件:", type=["txt",  "ztm", "sparameters"], accept_multiple_files=True)
spice_model_path = st.text_input('请输入spice模型文件存储路径（可以不设置，默认为当前工程目录）', max_chars=100, help='最大长度为100字符')
# 检查路径是否为空
if spice_model_path:
    # 如果路径不合法，提示用户重新输入
    if not is_valid_path(spice_model_path):
        st.error(f"路径 '{spice_model_path}' 不合法！请确保路径存在且是文件夹或文件。")
    else:
        st.success(f"路径 '{spice_model_path}' 合法！")
Z_f_n_n_list = []
fre_list = []
if len(uploaded_file_set) > 3:
    for uploaded_file in uploaded_file_set:
        st.write(uploaded_file.name)
        file_name, file_extension = os.path.splitext(uploaded_file.name)
        print("文件名:", file_name)  # 输出: 文件名: /home/user/documents/example
        print("扩展名:", file_extension)  # 输出: 扩展名: .txt
        match file_extension:
            case ".txt":
                dataframe = pd.read_csv(uploaded_file, delimiter=',', header=None)
                st.write(dataframe)
                # 假设文件中的列已经包含复数形式的字符串
                # 将字符串转换为复数类型
                df_complex = dataframe.applymap(to_complex)
                arr = df_complex.to_numpy()
                opts["asymp"] = 3  # Modified to include D and E in fitting
                opts["phaseplot"] = True  # Modified to include the phase angle graph
                N = arr.shape[1]
                weights = np.ones(N, dtype=np.float64)
                n = 3
                # Order of aproximation
                poles = -2 * pi * np.logspace(0, 4, n, dtype=np.complex128)  # Initial searching poles
                arr = np.transpose(arr)
                s = arr[:, 0]
                f = arr[:, 1]
                (SER, poles, rmserr, fit) = vectfit(f, s, poles, weights, opts)
                ####
            case ".ztm":
                ztm_file = uploaded_file#"E:\公司工作（低空防御）\场路仿真\场路转换算法\Composite_ZCM_3\Composite_ZCM_Configuration.xml"
                result_data,fre_data = wyz_io.read_matrix_from_txt(ztm_file)
                Z_f_n_n_list.append(result_data)
                fre_list.append(fre_data)
                inut_file_type = 1
            case ".sparameters":
                ztm_file = uploaded_file  # "E:\公司工作（低空防御）\场路仿真\场路转换算法\Composite_ZCM_3\Composite_ZCM_Configuration.xml"
                result_data, fre_data = wyz_io.read_matrix_from_txt(ztm_file)
                Z_f_n_n_list.append(result_data)
                fre_list.append(fre_data)
                inut_file_type = 2

            case _:
                print("文件格式错误")
    #####这里需要对数据进行排序
    frequency_ordered_index = np.argsort(fre_list)  ####Z矩阵也需要按照这个进行处理
    Z_f_n_n_list_ordered=[]
    frequency_ordered = []
    for fer_ordered in frequency_ordered_index:
        Z_f_n_n_list_ordered.append(Z_f_n_n_list[fer_ordered])
        frequency_ordered.append(fre_list[fer_ordered])
    Z_fnn_matrix = np.stack(Z_f_n_n_list_ordered, axis=0)
    is_data_ready = 1
else:
    print("文件数量太少:")
    st.write("当前文件数量:", len(uploaded_file_set))
    is_data_ready = 0
    st.text("文件数量太少,请重新输入")
####2. 这里需要进行场路转化，点击按钮之后feild2cuirt_start的值为1

# 标题
st.title("场路转换模式选择")
# 创建选项卡
tab1, tab2 = st.tabs(["自动模式", "手动模式"])
# 自动模式
with tab1:
    st.header("自动模式参数设置")
    spice_content = ""

    # 使用 st.columns 将输入框分成多列
    col1, col2, col3 = st.columns(3)

    with col1:
        n_poles_init_real = st.number_input(
            "初始实数极点数量 (n_poles_init_real)",
            min_value=1,
            value=3,
            step=1,
            key="auto_n_poles_init_real"  # 唯一的 key
        )
        n_poles_init_cmplx = st.number_input(
            "初始复数极点数量 (n_poles_init_cmplx)",
            min_value=1,
            value=3,
            step=1,
            key="auto_n_poles_init_cmplx"  # 唯一的 key
        )
        n_poles_add = st.number_input(
            "每次增加的极点数量 (n_poles_add)",
            min_value=1,
            value=3,
            step=1,
            key="auto_n_poles_add"  # 唯一的 key
        )

    with col2:
        model_order_max = st.number_input(
            "最大模型阶数 (model_order_max)",
            min_value=1,
            value=100,
            step=1,
            key="auto_model_order_max"  # 唯一的 key
        )
        iters_start = st.number_input(
            "初始拟合迭代次数 (iters_start)",
            min_value=1,
            value=3,
            step=1,
            key="auto_iters_start"  # 唯一的 key
        )
        iters_inter = st.number_input(
            "中间拟合迭代次数 (iters_inter)",
            min_value=1,
            value=3,
            step=1,
            key="auto_iters_inter"  # 唯一的 key
        )

    with col3:
        iters_final = st.number_input(
            "最终拟合迭代次数 (iters_final)",
            min_value=1,
            value=5,
            step=1,
            key="auto_iters_final"  # 唯一的 key
        )
        target_error = st.number_input(
            "目标误差 (target_error)",
            min_value=0.0,
            value=1e-2,
            format="%.5f",
            key="auto_target_error"  # 唯一的 key
        )
        alpha = st.number_input(
            "正则化参数 alpha",
            min_value=0.0,
            value=0.03,
            format="%.3f",
            key="auto_alpha"  # 唯一的 key
        )

    # 使用 st.expander 将可选参数折叠起来
    with st.expander("高级参数设置"):
        gamma = st.number_input(
            "正则化参数 gamma",
            min_value=0.0,
            value=0.03,
            format="%.3f",
            key="auto_gamma"  # 唯一的 key
        )
        nu_samples = st.number_input(
            "采样密度 (nu_samples)",
            min_value=0.0,
            value=1.0,
            format="%.1f",
            key="auto_nu_samples"  # 唯一的 key
        )
        parameter_type = st.selectbox(
            "参数类型 (parameter_type)",
            options=['s'],
            index=0,  # 默认选择 's'
            key="auto_parameter_type"  # 唯一的 key
        )
        compare_flag_on = st.toggle("启用结果自动比较功能（S11），", value=True)  # 返回 True/False

    # 开始拟合按钮
    if st.button("开始自动转换"):
        if is_data_ready == 0:
            st.text("请输入阻抗数据")
        else:
            if inut_file_type==1:
                ntw = rf.Network(frequency=np.array(frequency_ordered) * 1e6, z=Z_fnn_matrix)
            else:
                ntw = rf.Network(frequency=np.array(frequency_ordered) * 1e6, s=Z_fnn_matrix)
            # ntw2 = rf.Network.from_z(Z_fnn_matrix,f=np.array(frequency_ordered) * 1e6)
            s_parameters = ntw.s
            # print(ntw)
            vf = rf.VectorFitting(ntw)
            # vf.vector_fit(n_poles_real=0, n_poles_cmplx=2, fit_constant=False)
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

            passive_flag = vf.is_passive()
            # vf.plot_convergence()
            # vf.passivity_enforce()  # won't do anything if model is already passive
            vf.write_spice_subcircuit_s('wyz2.sp')
            spice_content = vf.generate_spice_subcircuit_s2()
            wyz_wucha = vf.get_rms_error(parameter_type='s')
            if compare_flag_on:
                frequecy_fit = np.linspace(0, frequency_ordered[-1]*1e6, len(frequency_ordered)*10)###单位是Mhz
                fit_data = vf.get_model_response(0, 0, frequecy_fit)

                Zij = fit_data;###50*(1+fit_data)/(1-fit_data)
                # 正确的方式：先创建figure和axes
                fig, ax = plt.subplots()
                # 绘制拟合结果
                ax.plot(frequecy_fit / 1e6, np.abs(Zij), label='Fitted Model')  # 转换为MHz单位
                # 绘制原始S参数（假设绘制S11）
                s11 = ntw.s[:, 0, 0]  # 获取S11参数
                ax.plot(frequency_ordered, np.abs(s11), 'o', label='Original Data')  # 绘制幅度

                ax.set_xlabel('Frequency (MHz)')
                ax.set_ylabel('Magnitude')
                ax.set_title('Model Response')
                ax.legend()
                ax.grid(True)
                # 设置x轴和y轴的显示范围
                #ax.set_xlim(0, 0.01)  # x轴范围：0 MHz 到 1000 MHz
                #ax.set_ylim(0, 0.2)  # y轴范围：0 到 1.2（假设幅度在0~1之间）
                st.pyplot(fig)

    # 将列表转换为字符串
    spice_content_str = spice_content
    # 选择存储方式
    storage_option = st.radio(
        "选择存储方式：",
        options=["下载到当前电脑", "存储到服务器本地"],
        index=0,  # 默认选择下载到当前电脑
        key="auto_storage_option"  # 唯一的 key
    )
    if len(spice_content_str)!=0:
        # 处理存储逻辑
        if storage_option == "下载到当前电脑":
            # 提供下载按钮
            st.download_button(
                label="下载 SPICE 文件",
                data=spice_content_str,
                file_name="example.cir",  # 下载文件的名称
                mime="text/plain"  # MIME 类型
            )
        else:
            # 存储到服务器本地
            default_path = os.path.join(os.getcwd(), "example.cir")  # 默认路径为当前工作目录下的 example.sp
            file_path = st.text_input("输入服务器本地存储路径：", value=default_path)

            if st.button("存储到服务器本地"):
                try:
                    # 确保目录存在
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    # 写入文件
                    with open(file_path, "w") as f:
                        f.write(spice_content)
                    st.success(f"文件已成功存储到：{os.path.abspath(file_path)}")
                except Exception as e:
                    st.error(f"存储文件时出错：{e}")


# 手动模式
with tab2:
    st.header("手动模式参数设置")

    spice_content = ""
    # 使用 st.columns 将输入框分成多列
    col1, col2 = st.columns(2)

    with col1:
        n_poles_real = st.number_input(
            "实数极点数量 (n_poles_real)",
            min_value=1,
            value=2,
            step=1,
            key="manual_n_poles_real"  # 唯一的 key
        )
        n_poles_cmplx = st.number_input(
            "复数极点数量 (n_poles_cmplx)",
            min_value=1,
            value=2,
            step=1,
            key="manual_n_poles_cmplx"  # 唯一的 key
        )
        init_pole_spacing = st.selectbox(
            "初始极点间距 (init_pole_spacing)",
            options=['lin', 'log'],
            index=0,  # 默认选择 'lin'
            key="manual_init_pole_spacing"  # 唯一的 key
        )

    with col2:
        parameter_type = st.selectbox(
            "参数类型 (parameter_type)",
            options=['s', 'z'],
            index=0,  # 默认选择 's'
            key="manual_parameter_type"  # 唯一的 key
        )
        fit_constant = st.checkbox(
            "拟合常数项 (fit_constant)",
            value=True,
            key="manual_fit_constant"  # 唯一的 key
        )
        fit_proportional = st.checkbox(
            "拟合比例项 (fit_proportional)",
            value=False,
            key="manual_fit_proportional"  # 唯一的 key
        )

    # 开始拟合按钮
    if st.button("开始手动拟合"):
        if is_data_ready==0:
            st.text("请输入阻抗数据")
        else:
            ntw = rf.Network(frequency=np.array(frequency_ordered) * 1e6, z=Z_fnn_matrix)
            # ntw2 = rf.Network.from_z(Z_fnn_matrix,f=np.array(frequency_ordered) * 1e6)
            s_parameters = ntw.s
            # print(ntw)
            vf = rf.VectorFitting(ntw)
            vf.vector_fit(n_poles_real=n_poles_real, n_poles_cmplx=n_poles_cmplx,
            init_pole_spacing=init_pole_spacing,
            parameter_type=parameter_type,
            fit_constant=fit_constant,
            fit_proportional=fit_proportional)
            #vf.auto_fit()
            if fit_proportional==False:
                passive_flag = vf.is_passive()
            # vf.plot_convergence()
            # vf.passivity_enforce()  # won't do anything if model is already passive
            frequecy_fit = np.linspace(0, 10e3, 21)
            fit_data = vf.get_model_response(0, 0, frequecy_fit)

            vf.write_spice_subcircuit_s('wyz2.cir')
            spice_content = vf.generate_spice_subcircuit_s2()
    # 将列表转换为字符串
    spice_content_str = spice_content
    # 选择存储方式
    storage_option = st.radio(
        "选择存储方式：",
        options=["下载到当前电脑", "存储到服务器本地"],
        index=0,  # 默认选择下载到当前电脑
        key="manual_storage_option"  # 唯一的 key
    )
    if len(spice_content_str) != 0:
        # 处理存储逻辑
        if storage_option == "下载到当前电脑":
            # 提供下载按钮
            st.download_button(
                label="下载 SPICE 文件",
                data=spice_content_str,
                file_name="example.cir",  # 下载文件的名称
                mime="text/plain"  # MIME 类型
            )
        else:
            # 存储到服务器本地
            default_path = os.path.join(os.getcwd(), "example.cir")  # 默认路径为当前工作目录下的 example.sp
            file_path = st.text_input("输入服务器本地存储路径：", value=default_path)

            if st.button("存储到服务器本地"):
                try:
                    # 确保目录存在
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    # 写入文件
                    with open(file_path, "w") as f:
                        f.write(spice_content)
                    st.success(f"文件已成功存储到：{os.path.abspath(file_path)}")
                except Exception as e:
                    st.error(f"存储文件时出错：{e}")





