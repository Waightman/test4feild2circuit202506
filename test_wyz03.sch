<Qucs Schematic 24.4.0>
<Properties>
  <View=0,0,1381,866,1,0,0>
  <Grid=10,10,1>
  <DataSet=test_wyz03.dat>
  <DataDisplay=test_wyz03.dpl>
  <OpenDisplay=0>
  <Script=test_wyz03.m>
  <RunScript=0>
  <showFrame=0>
  <FrameText0=标题>
  <FrameText1=绘制者：>
  <FrameText2=日期：>
  <FrameText3=修订：>
</Properties>
<Symbol>
</Symbol>
<Components>
  <SPICE X1 1 600 260 -26 -49 0 0 "E:/pycharm_python/ZH_project_v1/ring_slot.sp" 1 "_netp1,_netp2" 0 "yes" 0 "none" 0>
  <Vac V2 1 890 350 18 -26 0 1 "1 V" 1 "1 kHz" 0 "0" 0 "0" 0 "0" 0 "0" 0>
  <Vac V1 1 280 360 18 -26 0 1 "1 V" 1 "1 kHz" 0 "0" 0 "0" 0 "0" 0 "0" 0>
  <R R1 1 420 260 -26 15 0 0 "1 kOhm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <R R2 1 740 260 -26 15 0 0 "1 kOhm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <GND * 1 280 430 0 0 0 0>
  <GND * 1 890 420 0 0 0 0>
  <.AC AC1 1 270 560 0 38 0 0 "lin" 1 "1 Hz" 1 "10 kHz" 1 "200" 1 "no" 0>
</Components>
<Wires>
  <890 260 890 320 "" 0 0 0 "">
  <770 260 890 260 "" 0 0 0 "">
  <450 260 570 260 "" 0 0 0 "">
  <630 260 710 260 "" 0 0 0 "">
  <280 260 390 260 "" 0 0 0 "">
  <280 260 280 330 "" 0 0 0 "">
  <280 390 280 430 "" 0 0 0 "">
  <890 380 890 420 "" 0 0 0 "">
</Wires>
<Diagrams>
</Diagrams>
<Paintings>
</Paintings>
