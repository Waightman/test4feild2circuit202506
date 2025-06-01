import xml.etree.ElementTree as ET
import re
import os
import numpy as np


def read_matrix_from_txt(file_path):
    matrix_data = []
    aaa = type(file_path)
    # 打开文件读取
    #with open(file_path, 'r') as file:
    file_content = file_path.read()
    # 将 bytes 解码为字符串
    file_content_str = file_content.decode("utf-8")
    for line in file_content_str.splitlines():
        # 跳过以#或>开头的行以及空白行
        if line.startswith('#') or line.startswith('>') or line.startswith('.')or line.strip() == '':
            continue

        # 处理数字行，转换为数字列表
        values = line.strip().split()
        matrix_data.append([float(v) for v in values])

    # 将列表转换为NumPy数组（矩阵）
    matrix = np.array(matrix_data)
    ####下面将其转化为方阵
    [num_row, num_coloum] = matrix.shape
    #####参数检测

    #####
    size_mat = int(np.sqrt(num_row))
    data_real = matrix[:, 3]
    data_imag = matrix[:, 4]
    mat_real = data_real.reshape((size_mat,size_mat))
    mat_imag = data_imag.reshape((size_mat, size_mat))
    matrix_complex = mat_real+mat_imag*1J

    frequecy_array = matrix[:, 0]
    frequecy_set = set(frequecy_array)
    return matrix_complex, list(frequecy_set)[0]


def read_ztm_data(xml_file_pathname):

    # 分离路径和文件名
    file_path = os.path.dirname(xml_file_pathname)
    file_name = os.path.basename(xml_file_pathname)
    tree = ET.parse(xml_file_pathname)
    root = tree.getroot()
    wyz = root.findall(".//Filename")

    # 查找所有 <name> 节点
    name_nodes = root.findall(".//name")

    # 正则表达式：匹配 Frequency 后跟任意单位（例如 MHz, GHz 或其他）
    pattern = re.compile(r"Frequency \[(.*?)\]")

    # 匹配节点文本
    for name_node in name_nodes:
        match = pattern.match(name_node.text)
        if match:
            print(f"Found {name_node.text} with unit: {match.group(1)}")

            # 获取关联的 <value> 节点
            value_node = name_node.find("./../value")  # 获取父节点的 <value> 节点
            if value_node is not None:
                print(f"  Value: {value_node.text}")

    Z_fnn_list = []
    for file in wyz:
        ztm_file = os.path.join(file_path, file.text)
        kk = read_matrix_from_txt(ztm_file)
        Z_fnn_list.append(kk)
    Z_fnn_matrix = np.stack(Z_fnn_list, axis=0)
    return Z_fnn_matrix

if __name__ == '__main__':
    xml_file_pathname = "E:\公司工作（低空防御）\场路仿真\场路转换算法\Composite_ZCM_3\Composite_ZCM_Configuration.xml"
    result_data = read_ztm_data(xml_file_pathname)
    wyz1111 = 1111

