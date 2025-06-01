* EQUIVALENT CIRCUIT FOR VECTOR FITTED S-MATRIX
* Created using scikit-rf vectorFitting.py

.SUBCKT s_equivalent p1 p2

* Port network for port 1
R_ref_1 p1 a1 50.0
H_b_1 a1 0 V_c_1 14.142135623730951
* Differential incident wave a sources for transfer from port 1
H_p_1 nt_p_1 nts_p_1 H_b_1 3.5355339059327378
E_p_1 nts_p_1 0 p1 0 0.07071067811865475
E_n_1 0 nt_n_1 nt_p_1 0 1
* Current sensor on center node for transfer to port 1
V_c_1 nt_c_1 0 0
* Transfer network from port 1 to port 1
R1_1 nt_n_1 nt_c_1 1.037827408268144
X1 nt_n_1 nt_c_1 rl_admittance res=28.299910501838912 ind=1.256404626648448e-11
X2 nt_p_1 nt_c_1 rcl_vccs_admittance res=1.1030686382504382 cap=4.960655656182164e-13 ind=6.928952926577126e-12 gm=0.0010277575423302539
* Transfer network from port 2 to port 1
R1_2 nt_n_2 nt_c_1 12.165983322770646
X3 nt_p_2 nt_c_1 rl_admittance res=70.91415832653782 ind=3.148309483542473e-11
X4 nt_p_2 nt_c_1 rcl_vccs_admittance res=0.9802555865023647 cap=5.582160157861028e-13 ind=6.1574997052423345e-12 gm=0.06622381178827576

* Port network for port 2
R_ref_2 p2 a2 50.0
H_b_2 a2 0 V_c_2 14.142135623730951
* Differential incident wave a sources for transfer from port 2
H_p_2 nt_p_2 nts_p_2 H_b_2 3.5355339059327378
E_p_2 nts_p_2 0 p2 0 0.07071067811865475
E_n_2 0 nt_n_2 nt_p_2 0 1
* Current sensor on center node for transfer to port 2
V_c_2 nt_c_2 0 0
* Transfer network from port 1 to port 2
R2_1 nt_n_1 nt_c_2 12.165983322770646
X5 nt_p_1 nt_c_2 rl_admittance res=70.91415832653782 ind=3.148309483542473e-11
X6 nt_p_1 nt_c_2 rcl_vccs_admittance res=0.9802555865023647 cap=5.582160157861028e-13 ind=6.1574997052423345e-12 gm=0.06622381178827576
* Transfer network from port 2 to port 2
R2_2 nt_p_2 nt_c_2 1.0697691625611134
X7 nt_n_2 nt_c_2 rl_admittance res=0.4809102350015705 ind=2.1350521381306267e-13
X8 nt_p_2 nt_c_2 rcl_vccs_admittance res=0.9268930912219163 cap=5.903532706539619e-13 ind=5.822301871652061e-12 gm=0.14460177756823106
.ENDS s_equivalent

.SUBCKT rcl_vccs_admittance n_pos n_neg res=1e3 cap=1e-9 ind=100e-12 gm=1e-3
L1 n_pos 1 {ind}
C1 1 2 {cap}
R1 2 n_neg {res}
G1 n_pos n_neg 1 2 {gm}
.ENDS rcl_vccs_admittance

.SUBCKT rl_admittance n_pos n_neg res=1e3 ind=100e-12
L1 n_pos 1 {ind}
R1 1 n_neg {res}
.ENDS rl_admittance

