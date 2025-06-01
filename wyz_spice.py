import ctypes
import os
from pathlib import Path
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
class wyz_spice:
    def __init__(self,dll_path_name=r"Spice64_dll44\dll-vs\ngspice.dll"):
        # 定义回调函数类型
        self.SendChar = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        self.SendStat = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        self.ControlledExit = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int,
                                          ctypes.c_void_p)
        self.SendData = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_int,
                                    ctypes.c_void_p)
        self.SendInitData = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_void_p)
        self.BGThreadRunning = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)

        # 加载Ngspice动态库
        self.ngspice_path = dll_path_name
        self.ngspice = ctypes.CDLL(self.ngspice_path)
        # 定义Ngspice的API函数
        self.ngspice.ngSpice_Init.argtypes = [self.SendChar, self.SendStat, self.ControlledExit, self.SendData, self.SendInitData, self.BGThreadRunning,
                                         ctypes.c_void_p]
        self.ngspice.ngSpice_Init.restype = ctypes.c_int

        self.ngspice.ngSpice_Command.argtypes = [ctypes.c_char_p]
        self.ngspice.ngSpice_Command.restype = ctypes.c_int

        self.ngspice.ngSpice_Circ.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
        self.ngspice.ngSpice_Circ.restype = ctypes.c_int

        self.ngspice.ngSpice_running.argtypes = []
        self.ngspice.ngSpice_running.restype = ctypes.c_bool

        self.ngspice.ngGet_Vec_Info.argtypes = [ctypes.c_char_p]
        self.ngspice.ngGet_Vec_Info.restype = ctypes.POINTER(ctypes.c_void_p)

        self.ngspice.ngSpice_CurPlot.argtypes = None
        self.ngspice.ngSpice_CurPlot.restype = ctypes.c_char_p

        # 指定 ngSpice_AllVecs 的参数类型和返回类型
        self.ngspice.ngSpice_AllVecs.argtypes = [ctypes.c_char_p]  # 传入的参数是 char* (C字符串)
        self.ngspice.ngSpice_AllVecs.restype = ctypes.POINTER(ctypes.c_char_p)  # 返回的是 char** (字符串指针数组)
        # 初始化Ngspice
        self.send_char_cb = self.SendChar(send_char)
        self.send_stat_cb = self.SendStat(send_stat)
        self.controlled_exit_cb = self.ControlledExit(controlled_exit)
        self.send_data_cb = self.SendData(send_data)
        self.send_init_data_cb = self.SendInitData(send_init_data)
        self.bg_thread_running_cb = self.BGThreadRunning(bg_thread_running)

        self.ngspice.ngSpice_Init(self.send_char_cb, self.send_stat_cb, self.controlled_exit_cb, self.send_data_cb, self.send_init_data_cb,
                             self.bg_thread_running_cb, None)


    def get_vecter_data(self, *args):
        # 获取频率和输出数据
        data_list = []
        x = args[0]
        if isinstance(x, bytes):
            freq_vector_info = self.ngspice.ngGet_Vec_Info(x)
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

                # 打印前 10 个频率和输出数据
                for i in range(freq_length):  # 防止越界
                    # 获取复数数据
                    freq_complex = freq_vector[i]  # 这里是ngcomplex_t类型
                    # 获取复数的实部和虚部
                    freq_real = freq_complex.real
                    freq_imag = freq_complex.imag
                    data_list.append(freq_real+1j*freq_imag)
        return data_list

    def spice_simulate(self, *args):
        #### 这个函数负责调用ngspice.dll, 仿真输入参数*args可以是list列表（每一行是一个spice语句，带换行符），也可以是sp文件的路径
        #### 处理输入的网表，可能是list也可能是文件路径
        if len(args) != 1:
            raise ValueError("只能接受一个参数")
        data = args[0]
        if isinstance(data, list):
            netlist_lines = data
        elif isinstance(data, str) and Path(data).is_file():
            with open(data, 'r', encoding='utf-8') as f:
                netlist_lines = f.readlines()
        else:
            raise ValueError("输入必须是列表或有效的文件路径")

        netlist_array = (ctypes.c_char_p * (len(netlist_lines) + 1))()
        for i, line in enumerate(netlist_lines):
            netlist_array[i] = line.strip().encode('utf-8')
        netlist_array[len(netlist_lines)] = None

        self.ngspice.ngSpice_Circ(netlist_array)
        # 运行AC仿真
        command_result = self.ngspice.ngSpice_Command(b"ac dec 10 100 1e6")
        if command_result != 0:
            print(f"Error running AC simulation command, error code: {command_result}")
        else:
            print("AC simulation command executed successfully")

        # 等待仿真完成
        while self.ngspice.ngSpice_running():
            pass
        # ngspice.ngSpice_Command(b"print v(node1) frequency")
        self.ngspice.ngSpice_Command(b"display")
        plotname = self.ngspice.ngSpice_CurPlot().decode().encode("utf-8")
        print(plotname)

        # 调用ngSpice_AllVecs获取所有向量名称
        #plotname = b"ac1"  # 用来获取所有向量的名称
        vector_names_ptr = self.ngspice.ngSpice_AllVecs(plotname)
        # 如果返回值不是 NULL，则可以继续处理返回的指针
        if vector_names_ptr:
            index = 0
            while vector_names_ptr[index] is not None:
                vector_name = ctypes.cast(vector_names_ptr[index], ctypes.c_char_p).value.decode('utf-8')
                print(f"Vector {index}: {vector_name}")
                index += 1
        else:
            print("No vectors found.")





if __name__== '__main__':
    temp = wyz_spice()
    temp.spice_simulate(r"E:\pycharm_python\test2.sp")
    f_wyz = temp.get_vecter_data(b"frequency")
    v_wyz = temp.get_vecter_data(b"v(P1)")
    print(f_wyz)
    print(v_wyz)
    # 清理
    temp.ngspice.ngSpice_Command(b"quit")










