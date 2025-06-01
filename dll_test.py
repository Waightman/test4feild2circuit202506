import ctypes
import os

# 定义回调函数类型
SendChar = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
SendStat = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
ControlledExit = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int,
                                  ctypes.c_void_p)
SendData = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_int, ctypes.c_void_p)
SendInitData = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_void_p)
BGThreadRunning = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)


# 定义回调函数
def send_char(char_string, id, user_data):
    print(char_string.decode('utf-8'))
    return 0


def send_stat(status_string, id, user_data):
    print(status_string.decode('utf-8'))
    return 0


def controlled_exit(exit_status, immediate_unload, exit_upon_quit, id, user_data):
    print(f"Controlled exit with status: {exit_status}")
    return 0


def send_data(data, num_structs, id, user_data):
    print("Data received")
    return 0


def send_init_data(data, id, user_data):
    print("Initialization data received")
    return 0


def bg_thread_running(is_running, id, user_data):
    print(f"Background thread running: {is_running}")
    return 0


# 加载Ngspice动态库
ngspice_path = r"E:\公司工作（低空防御）\场路仿真\web开发\Spice64_dll\dll-vs\ngspice.dll"  # 替换为你的Ngspice动态库路径
ngspice = ctypes.CDLL(ngspice_path)

# 定义Ngspice的API函数
ngspice.ngSpice_Init.argtypes = [SendChar, SendStat, ControlledExit, SendData, SendInitData, BGThreadRunning,
                                 ctypes.c_void_p]
ngspice.ngSpice_Init.restype = ctypes.c_int

ngspice.ngSpice_Command.argtypes = [ctypes.c_char_p]
ngspice.ngSpice_Command.restype = ctypes.c_int

ngspice.ngSpice_Circ.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
ngspice.ngSpice_Circ.restype = ctypes.c_int

ngspice.ngSpice_running.argtypes = []
ngspice.ngSpice_running.restype = ctypes.c_bool

ngspice.ngGet_Vec_Info.argtypes = [ctypes.c_char_p]
ngspice.ngGet_Vec_Info.restype = ctypes.POINTER(ctypes.c_void_p)

ngspice.ngSpice_CurPlot.argtypes = None
ngspice.ngSpice_CurPlot.restype = ctypes.c_char_p

# 指定 ngSpice_AllVecs 的参数类型和返回类型
ngspice.ngSpice_AllVecs.argtypes = [ctypes.c_char_p]  # 传入的参数是 char* (C字符串)
ngspice.ngSpice_AllVecs.restype = ctypes.POINTER(ctypes.c_char_p)  # 返回的是 char** (字符串指针数组)


# 定义复数类型 ngcomplex_t
class ngcomplex_t(ctypes.Structure):
    _fields_ = [("real", ctypes.c_double), ("imag", ctypes.c_double)]


# 定义结构体 vector_info
class vector_info(ctypes.Structure):
    _fields_ = [
        ("v_name", ctypes.c_char_p),
        ("v_type", ctypes.c_int),
        ("v_flags", ctypes.c_short),
        ("v_realdata", ctypes.POINTER(ctypes.c_double)),
        ("v_compdata", ctypes.POINTER(ngcomplex_t)),
        ("v_length", ctypes.c_int)
    ]


# 初始化Ngspice
send_char_cb = SendChar(send_char)
send_stat_cb = SendStat(send_stat)
controlled_exit_cb = ControlledExit(controlled_exit)
send_data_cb = SendData(send_data)
send_init_data_cb = SendInitData(send_init_data)
bg_thread_running_cb = BGThreadRunning(bg_thread_running)

ngspice.ngSpice_Init(send_char_cb, send_stat_cb, controlled_exit_cb, send_data_cb, send_init_data_cb,
                     bg_thread_running_cb, None)

# 加载网表文件
netlist_path = r"E:\pycharm_python\test.sp"  # 替换为你的网表文件路径
with open(netlist_path, 'r') as f:
    netlist_lines = f.readlines()

netlist_array = (ctypes.c_char_p * (len(netlist_lines) + 1))()
for i, line in enumerate(netlist_lines):
    netlist_array[i] = line.strip().encode('utf-8')
netlist_array[len(netlist_lines)] = None

ngspice.ngSpice_Circ(netlist_array)

# 运行AC仿真
command_result = ngspice.ngSpice_Command(b"ac dec 10 100 1e6")
if command_result != 0:
    print(f"Error running AC simulation command, error code: {command_result}")
else:
    print("AC simulation command executed successfully")

# 等待仿真完成
while ngspice.ngSpice_running():
    pass
# ngspice.ngSpice_Command(b"print v(node1) frequency")
ngspice.ngSpice_Command(b"display")
print(ngspice.ngSpice_CurPlot().decode())

# 调用ngSpice_AllVecs获取所有向量名称
plotname = b"ac1"  # 用来获取所有向量的名称
vector_names_ptr = ngspice.ngSpice_AllVecs(plotname)
# 如果返回值不是 NULL，则可以继续处理返回的指针
if vector_names_ptr:
    index = 0
    while vector_names_ptr[index] is not None:
        vector_name = ctypes.cast(vector_names_ptr[index], ctypes.c_char_p).value.decode('utf-8')
        print(f"Vector {index}: {vector_name}")
        index += 1
else:
    print("No vectors found.")
# 获取频率和输出数据
freq_vector_info = ngspice.ngGet_Vec_Info(b"frequency")
if freq_vector_info:
    # 将返回的指针转换为 vector_info 结构体类型
    freq_vector_info_struct = ctypes.cast(freq_vector_info, ctypes.POINTER(vector_info)).contents
    # 获取数据长度
    freq_length = freq_vector_info_struct.v_length
    # 获取v_realdata指针并再次转换为正确的类型
    if freq_vector_info_struct.v_compdata:
        freq_vector = ctypes.cast(freq_vector_info_struct.v_compdata, ctypes.POINTER(ngcomplex_t))
    else:
        print("Error: Frequency vector data is NULL.")
        freq_vector = None

output_vector_info = ngspice.ngGet_Vec_Info(b"v(node6)")

if output_vector_info:
    # 将返回的指针转换为 vector_info 结构体类型
    output_vector_info_struct = ctypes.cast(output_vector_info, ctypes.POINTER(vector_info)).contents

    # 获取数据长度
    output_length = output_vector_info_struct.v_length
    # 获取v_realdata指针并再次转换为正确的类型
    if output_vector_info_struct.v_compdata:
        output_vector = ctypes.cast(output_vector_info_struct.v_compdata, ctypes.POINTER(ngcomplex_t))
    else:
        print("Error: Output vector data is NULL.")
        output_vector = None

    # # 访问实际数据
    # freq_vector = freq_vector_info_struct.v_compdata
    # output_vector = output_vector_info_struct.v_compdata

    # 打印前 10 个频率和输出数据
    for i in range(min(10, freq_length, output_length)):  # 防止越界
        # 获取复数数据
        freq_complex = freq_vector[i]  # 这里是ngcomplex_t类型
        output_complex = output_vector[i]  # 这里是ngcomplex_t类型

        # 获取复数的实部和虚部
        freq_real = freq_complex.real
        freq_imag = freq_complex.imag
        output_real = output_complex.real
        output_imag = output_complex.imag

        # 打印频率和输出的实部、虚部
        print(f"Frequency: {freq_real:.2f} + {freq_imag:.2f}j Hz, Output: {output_real:.2f} + {output_imag:.2f}j V")
        # print(f"Frequency: {freq_vector[i]:.2f} Hz, Output: {output_vector[i]:.2f} V")
else:
    print("Failed to get simulation results.")

# 清理
ngspice.ngSpice_Command(b"quit")
