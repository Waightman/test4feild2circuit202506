import matplotlib.pyplot as mplt
import numpy as np

import skrf

nw = skrf.data.ring_slot
vf = skrf.VectorFitting(nw)
vf.vector_fit(n_poles_real=3, n_poles_cmplx=0)

vf.write_spice_subcircuit_s('ring_slot.sp')


