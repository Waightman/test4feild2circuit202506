import numpy as np
import matplotlib.pyplot as plt
from matplotlib import pyplot as plt
import PySpice.Logging.Logging as Logging
import streamlit as st
import tempfile
import os
logger = Logging.setup_logging()

from PySpice.Spice.Netlist import Circuit
import re
from PySpice.Spice.NgSpice.Shared import NgSpiceShared
import wyz_spice
import math
# 设置 NGSpice 动态库的路径
#os.environ['PYSPICE_NGSPICE_LIB'] = 'E:\\pycharm_python\\ZH_project_v1\\PySpice_wyz\\PySpice\\Spice\\NgSpice\\Spice64_dll\\dll-vs\\ngspice.dll'

def parse_spice_file(sp_file_path):
    # 打开并读取SPICE文件
    with open(sp_file_path, 'r') as file:
        spice_data = file.readlines()

    # 查找所有的.SUBCKT定义，并提取名称和端口
    subckt_info = []
    subckt_name = None
    ports = []

    for line in spice_data:
        line = line.strip()  # 去除行两边的空格
        if line.startswith('*') or not line:  # 跳过注释行和空行
            continue
        if line.startswith('.SUBCKT'):
            # 解析子电路名称和端口
            match = re.match(r'\.SUBCKT\s+(\S+)\s+(.*)', line)
            if match:
                subckt_name = match.group(1)  # 获取子电路名称
                ports = match.group(2).split()  # 获取端口列表
                subckt_info.append({'subckt_name': subckt_name, 'ports': ports})

    return subckt_info


# 展示一级标题
st.header('1. spice 电路仿真')
st.text('本部分对等效文件模型进行简单的仿真验证，同时设置SPICE软件的启动与设置等参数')
# 输入起始频率和终止频率
start_frequency = st.number_input('仿真起始频率 (Hz)', min_value=1.0, max_value=1e9, value=1.0)
end_frequency = st.number_input('仿真终止频率 (Hz)', min_value=1.0, max_value=1e9, value=1e6)
# 选择扫描方法
scan_method = st.selectbox('选择扫描方法', ['liner', 'log'])
# 仿真方法，默认采用直接调用dll的方式，备选为pyspice
simulate_method4spice = st.selectbox('选择仿真方法', [1, 2])

### 场路转化模块
####1. 定义一个文件长传按钮，支持的类型暂定为cir与sp两种类型
uploaded_file = st.file_uploader("选择文件:", type=["cir", "sp"])
#feild2cuirt_start = st.button("文件仿真验证")
if uploaded_file is not None:
    # 读取文件内容
    file_content = uploaded_file.read().decode("utf-8")

    # 创建临时目录并保存文件
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(temp_file_path, "w") as f:
            f.write(file_content)

        st.write(f"文件已保存到: {temp_file_path}")
        # 检查文件是否存在
        if os.path.exists(temp_file_path):
            st.write(f"文件已成功保存到: {temp_file_path}")
        else:
            st.error(f"文件保存失败: {temp_file_path}")
            st.stop()  # 如果文件保存失败，停止执行

        # 创建电路对象
        circuit = Circuit('Voltage Divider')

        sp_file_name = temp_file_path  # 'E:\pycharm_python\pythonProject\wyz2.sp'
        # 引入 SP 文件中的元件
        circuit.include(sp_file_name)  # 替换为实际路径

        # 设定电路模型，实例化子电路
        ###需要分析sp文件，确定等效电路的名字以及端口的数量与名字
        sp_file_path = sp_file_name  # 替换为你的SPICE文件路径
        subcircuit_info = parse_spice_file(sp_file_path)

        # circuit.X('U1', 's_equivalent', 'p1')
        ports_name_string = ''
        for itme in subcircuit_info[0]['ports']:
            ports_name_string = ports_name_string + itme + ' '
        circuit.X('U1', subcircuit_info[0]['subckt_name'], ports_name_string)

        s_equivalent_ports = subcircuit_info[0]['ports']
        s_equivalent_ports_number = len(s_equivalent_ports)
        # 设置AC信号源（使用一个小幅度的AC源）
        for i in range(0, s_equivalent_ports_number):
            circuit.SinusoidalVoltageSource(1 + i, 'node' + str(i + 1), circuit.gnd,
                                            amplitude=2.0,
                                            frequency=1e3,
                                            offset=2.5)
            # 添加负载电阻
            #circuit.R(i + 1, s_equivalent_ports[i], 'node' + str(i + 1), 50)
            circuit.R(i + 1, 'node' + str(i + 1), 'pnode'+str(i + 1), 50)
            circuit.V('pionter'+str(i+1), 'pnode'+str(i + 1), s_equivalent_ports[i], 0)

        # 确保地节点存在
        #circuit.gnd = 0  # Explicitly setting ground as node 0, can be omitted if default ground is acceptable
        wyz_circuit = circuit.str_end()
        wyz_lines = wyz_circuit.splitlines()
        lines_with_newline = [line + os.linesep for line in wyz_lines]
        wyz_line_num = len(wyz_lines)
        print(str(circuit))

        if simulate_method4spice ==2:        # 进行AC分析
            # 选择仿真类型进行交流分析
            simulator = circuit.simulator(temperature=25, nominal_temperature=25)
            simulator.options(
                reltol=1e-3,  # 相对容差
                abstol=1e-6,  # 绝对容差
                vntol=1e-6,  # 电压容差
                max_num_iterations=100
            )
            analysis = simulator.ac(start_frequency=start_frequency, stop_frequency=end_frequency, number_of_points=100, variation='lin')
            # 获取S参数结果，计算反射和传输系数
            # 例如，假设电路有两个端口，计算S11和S21
            S11 = analysis['p1'] / analysis['v1']  # 反射系数 S11
            S21 = analysis['p1'] / analysis['v1']  # 传输系数 S21，调整计算方式根据具体需求

            # 绘制S参数的幅度和相位
            frequencies = analysis.frequency

            # 绘制S11
            fig = plt.figure(figsize=(10, 6))
            plt.subplot(2, 1, 1)
            plt.plot(frequencies, 20 * np.log10(np.abs(S11)), label="S11 Magnitude (dB)")
            plt.title('S-parameters Magnitude')
            plt.xlabel('Frequency [Hz]')
            plt.ylabel('Magnitude [dB]')
            plt.grid(True)

            # 绘制S21
            plt.subplot(2, 1, 2)
            plt.plot(frequencies, 20 * np.log10(np.abs(S21)), label="S21 Magnitude (dB)")
            plt.title('S-parameters Magnitude')
            plt.xlabel('Frequency [Hz]')
            plt.ylabel('Magnitude [dB]')
            plt.grid(True)

            plt.tight_layout()
            # plt.show()
            st.pyplot(fig)
            tam = 1000
        else:
            temp = wyz_spice.wyz_spice()
            temp.spice_simulate(lines_with_newline)
            f_wyz = temp.get_vecter_data(b"frequency")
            f_wyz_array = np.array(f_wyz)
            v_wyz = temp.get_vecter_data(b"v(P1)")
            v_wyz_array = np.array(v_wyz)
            current_wyz = temp.get_vecter_data(b"I(vpionter1)")
            current_wyz_array = np.array(current_wyz)
            z0 = 50
            a = 0.5/math.sqrt(z0)*(v_wyz_array+current_wyz_array*z0)
            b = 0.5/math.sqrt(z0)*(v_wyz_array-current_wyz_array*z0)
            saa = b/a
            print(f_wyz)
            fig = plt.figure(figsize=(10, 6))
            plt.plot(np.abs(f_wyz), 20 * np.log10(np.abs(saa)), label="S11 Magnitude (dB)")
            st.pyplot(fig)
            kk = 20 * np.log10(np.abs(saa))
            # 清理
            temp.ngspice.ngSpice_Command(b"quit")










