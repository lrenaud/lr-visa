#!/usr/bin/env python3

import psuN6705B
from engineering_notation import *
import json
from psuN6705B import PSU_Sample

h=psuN6705B.psuN6705B(DRY=False)

h.setOutVoltMaxAll(1.15)	# Set overvoltage protection limits
h.setOutVRangeMinAll()		# set each supply to its lowest voltage range
h.setOutIRangeMinAll()		# set each supply to its lowest current range
h.setOutILimitAll(0.1e-3)		# (TRY to) set current max to 0.1mA

print("V_out MAX settings: ", h.getOutVoltMaxAll())
print("I_limit settings: ", h.getOutILimitAll())
print("Raw measurements: ", h.getDatAll())

