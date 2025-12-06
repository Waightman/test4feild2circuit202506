import pandas as pd
import vectorfit_wyz as rf
import matplotlib.pyplot as mplt
import numpy as np
# 读取文件，使用空格作为分隔符，多个空格视为一个分隔符
df = pd.read_csv('E:\\公司工作（低空防御）\\场路仿真\\结题\\filter2-fushu.csv')

# 或者明确指定分隔符
# df = pd.read_csv('filter1.csv', sep='\s+')  # \s+ 表示一个或多个空白字符

aa = df.values
freq_list = aa[:,0]
# 创建 Frequency 对象
freq = rf.Frequency.from_f(freq_list, unit='ghz')
S_matrix_real= aa[:,1:9:2]
S_matrix_imag= aa[:,2:9:2]
# 功率分贝转线性功率
#S_matrix_power = 10**(S_matrix_db / 10)

# 假设零相位，转换为复数值
#S_matrix_magnitude = np.sqrt(S_matrix_power)
S_matrix = S_matrix_real + 1j*S_matrix_imag
# 如果S矩阵是 (n,4) 形状（对于2端口网络）
# 需要重塑为 (n,2,2)
if S_matrix.shape[1] == 4:  # 每行是 [S11, S12, S21, S22]
    npoints = S_matrix.shape[0]
    S_matrix_reshaped = S_matrix.reshape(npoints, 2, 2)
    nw = rf.Network(frequency=freq, s=S_matrix_reshaped, name='2-port')

print(df.head())
print(df.shape)


vf = rf.VectorFitting(nw)
#vf.vector_fit(n_poles_real=3, n_poles_cmplx=0)
vf.auto_fit()
vf.plot_convergence()
# 拟合完成后，可以直接从vf对象获取拟合后的网络
fitted_network = vf.network

# 获取拟合后的S参数矩阵（复数形式）
fitted_s = fitted_network.s  # 形状为 (n_freq, 2, 2)



rms_value = vf.get_rms_error()
print(rms_value)

print(vf.is_passive())
vf.passivity_enforce()
print(vf.is_passive())

# plot fitting results
freqs = freq_list
fig, ax = mplt.subplots(2, 2)
fig.set_size_inches(12, 8)
#vf.plot_s_db(0, 0, freqs=freqs, ax=ax[0][0]) # s11
# 获取原始数据的S参数（分贝值）
# 获取特定端口的S参数
s11_fitted = fitted_s[:, 0, 0]  # S11
# 在同一个图上绘制原始数据
#ax[0][0].plot(freqs*1e9, s_orig_db, 'g--', alpha=0.7, linewidth=1, label='原始数据')
# 在同一个图上绘制原始数据
#ax[0][0].plot(freqs*1e9, s11_fitted_db, 'r', alpha=0.7, linewidth=1, label='原始数据')
vf.plot_s_db(0, 0, freqs=freqs*1e9, ax=ax[0][0]) # s11
vf.plot_s_db(0, 1, freqs=freqs*1e9, ax=ax[0][1]) # s12
vf.plot_s_db(1, 0, freqs=freqs*1e9, ax=ax[1][0]) # s21
vf.plot_s_db(1, 1, freqs=freqs*1e9, ax=ax[1][1]) # s22
fig.tight_layout()
mplt.show()






# plot singular values of vector fitted scattering matrix
freqs = freq_list
fig, ax = mplt.subplots(1, 1)
fig.set_size_inches(6, 4)
vf.plot_s_singular(freqs=freqs, ax=ax)
fig.tight_layout()
mplt.show()
vf.write_spice_subcircuit_s2('filter2_wyz.sp')