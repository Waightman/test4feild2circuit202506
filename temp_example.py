import matplotlib.pyplot as mplt
import numpy as np

import vectorfit_wyz as rf
import matplotlib.pyplot as mplt
import numpy as np

'''
nw = rf.data.ring_slot
vf = rf.VectorFitting(nw)
vf.vector_fit(n_poles_real=3, n_poles_cmplx=0)

wyz = vf.get_rms_error()
print(wyz)
freqs1 = np.linspace(0, 200e9, 201)
fig, ax = mplt.subplots(2, 2)
fig.set_size_inches(12, 8)
vf.plot_s_mag(0, 0, freqs1, ax=ax[0][0]) # plot s11
vf.plot_s_mag(1, 0, freqs1, ax=ax[1][0]) # plot s21
vf.plot_s_mag(0, 1, freqs1, ax=ax[0][1]) # plot s12
vf.plot_s_mag(1, 1, freqs1, ax=ax[1][1]) # plot s22
fig.tight_layout()
mplt.show()

#vf.write_spice_subcircuit_s('ring_slot.sp')

'''
# load and fit the ring slot network with 3 poles
nw = rf.data.ring_slot
vf = rf.VectorFitting(nw)
vf.vector_fit(n_poles_real=3, n_poles_cmplx=0)

# plot fitting results
freqs = np.linspace(0, 200e9, 201)
fig, ax = mplt.subplots(2, 2)
fig.set_size_inches(12, 8)
vf.plot_s_mag(0, 0, freqs=freqs, ax=ax[0][0]) # s11
vf.plot_s_mag(0, 1, freqs=freqs, ax=ax[0][1]) # s12
vf.plot_s_mag(1, 0, freqs=freqs, ax=ax[1][0]) # s21
vf.plot_s_mag(1, 1, freqs=freqs, ax=ax[1][1]) # s22
fig.tight_layout()
mplt.show()
vf.get_rms_error()
print(vf.is_passive())
vf.passivity_enforce()
print(vf.is_passive())
# plot singular values of vector fitted scattering matrix
freqs = np.linspace(0, 200e9, 201)
fig, ax = mplt.subplots(1, 1)
fig.set_size_inches(6, 4)
vf.plot_s_singular(freqs=freqs, ax=ax)
fig.tight_layout()
mplt.show()
vf.write_spice_subcircuit_s2('FSS_wyz.sp')
