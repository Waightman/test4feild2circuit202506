import matplotlib.pyplot as plt
import scipy.io as sio
from vectfit3 import vectfit
from vectfit3 import opts
from scipy.constants import pi
#import vectorfit_wyz as rf
import skrf as rf
import numpy as np
# 读取.mat文件
mat_data = sio.loadmat(r'E:\公司工作（低空防御）\场路仿真\场路转换算法\vfit3\wyz_antennapattern.mat')

# 提取变量
matrix1 = mat_data['antenna_pattern_ori'].squeeze()
# 显示变量信息
print("matrix1的形状:", matrix1.shape)
frequency_ordered = np.linspace(0.5*pi, 1.5*pi, num=129)
ntw = rf.Network(frequency=frequency_ordered, s=matrix1)
# ntw2 = rf.Network.from_z(Z_fnn_matrix,f=np.array(frequency_ordered) * 1e6)
s_parameters = ntw.s
# print(ntw)
vf = rf.VectorFitting(ntw)
# vf.vector_fit(n_poles_real=0, n_poles_cmplx=2, fit_constant=False)
vf.auto_fit(target_error = 1e-2)
wyz = vf.get_rms_error(0,0)
passive_flag = vf.is_passive()
# vf.plot_convergence()
# vf.passivity_enforce()  # won't do anything if model is already passive
frequecy_fit = frequency_ordered
fit_data = vf.get_model_response(0, 0, frequecy_fit)
ori_data = matrix1
fit_data1 = 20*np.log10(np.abs(fit_data))
ori_data1 = 20*np.log10(np.abs(ori_data))
plt.plot(frequecy_fit,fit_data1)
plt.plot(frequecy_fit,ori_data1)
min_x = 0.5*pi
max_x = 1.5*pi
plt.xlim((min_x, max_x))
plt.ylim((-30, 0))
plt.show()
print(len(vf.poles))
print(wyz)

###问题1  阵列单元的数量需要与空间采样点的数量基本相等，才能得到差不多的结果，这是为什么？？？？
###问题2  采用这种有理分式的形式，如何与阵因子进行对应。


