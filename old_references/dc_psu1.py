#!/usr/bin/env python3

# Linux Depdnacnies
#######################
# sudo -H pip3 install python-usbtmc pyusb
# sudo -H pip3 install numpy 
# under linux, create a usbtmc group, and add your user to that group
## i.e. $ sudo chmod groupadd usbtmc
#       $ sudo usermod -aG usbtmc <your username>
# then logout and login to make the changes take effect.
#
# now add the following udev rule to a file (example name shown)
## /etc/udev/rules.d/usbtmc.rules
# SUBSYSTEMS=="usb", ACTION=="add", ATTRS{idVendor}=="0957", GROUP="usbtmc", MODE="0660"
###
# Now you're set to go!

import usbtmc
from time import sleep
from engineering_notation import *

class dc_psu1():
	supNum=1
	MAX_SUP_GLOBAL = 4;
	def __init__(self, DRY=True):
		self.DRY = DRY;
		if (self.DRY==False):
			self.psu=usbtmc.Instrument(0x0957, 0x0f07)
		# Tie into the USB interface fpr the N6705B
		print(self.ask("*IDN?"))
		self.pre_wait()

	######################
	## Reset
	## reset the device (everything)
	def rst(self):
		print("PSU: Reset called.")
		self.write("*RST")
	def reset(self):
		self.rst()
	def clear(self):
		print("PSU: clear called.")
		self.write("*CLS")
	def pre_wait(self):
		print("PSU: configuring OPC")
		self.write("*OPC")
	def wait(self, quiet=False):
		if(not quiet):
			print("PSU: Waiting for sync.")
		while(self.ask("*OPC?") == '0'):
			sleep(10e-3)
		if(not quiet):
			print("     cleared wait.")

	######################
	## Output Enable/Disable
	def setOutToggle(self, supNum):
		if getOutState(supNum):
			setOutOn(supNum)
		else:
			setOutOff(supNum)
			
	# Fetch output on/off
	def getOutState(self, supNum):
		return bool(self.psu.ask("OUTPut? (@%d)"% supNum))

	def setOutOn(self, supNum):
		self.write("OUTPut ON,(@%d)"% supNum)

	def setOutOff(self, supNum):
		self.write("OUTPut OFF,(@%d)"% supNum)

	######################
	## Control Maximum Current/Voltage Limtis
	def setOutVoltMax(self, volt, supNum):
		print("PSU: Setting %d VMAX = %g" % (supNum, volt))
		self.write("VOLTage:PROT %f,(@%d)"% (volt, supNum))

	def setOutVoltMaxALL(self, volt, maxSup = MAX_SUP_GLOBAL):
		print("PSU: Setting all VMAX = %g" % volt)
		self.write("VOLTage:PROT %f,(@1:%d)"% (volt, maxSup))

	def setOutILimit(self, imax, supNum):
		print("PSU: Setting %d IMAX = %g" % (supNum, imax))
		self.write("CURRent %f,(@%d)"% (imax, supNum))

	def setOutILimitAll(self, imax, maxSup = MAX_SUP_GLOBAL):
		print("PSU: Setting all IMAX = %g" % (imax))
		self.write("CURRent %f,(@1:%d)"% (imax, maxSup))
		
	######################
	## Fetch and set ranges to mimums
	def setOutVRangeMin(self, supNum):
		voltMinRange = float(\
			self.ask("VOLTage:RANGe? MIN,(@%d)"% supNum))
		self.write("VOLTage:RANG %f,(@%d)"% (voltMinRange, supNum))

	def setOutVRangeMinAll(self, maxSup = MAX_SUP_GLOBAL):
		voltMinRangesStr = self.ask("VOLTage:RANGe? MIN,(@1:%d)"% maxSup)
		voltMinRanges = list(map(float,voltMinRangesStr.split(',')))
		for n,volt in enumerate(voltMinRanges):
			self.write("VOLTage:RANG %f,(@%d)"% (volt, n+1))

	def setOutIRangeMin(self, supNum):
		currMinRange = float(\
			self.ask("CURRent:RANGe? MIN,(@%d)"% supNum))
		self.write("CURRent:RANG %f,(@%d)"% (currMinRange, supNum))

	def setOutIRangeMinAll(self, maxSup = MAX_SUP_GLOBAL):
		currMinRangesStr = self.ask("CURRent:RANGe? MIN,(@1:%d)"% maxSup)
		currMinRanges = list(map(float,currMinRangesStr.split(',')))
		for n,curr in enumerate(currMinRanges):
			self.write("CURRent:RANG %f,(@%d)"% (curr, n+1))


	######################
	# Core setting
	def setOutVolt(self, supNum, volt):
		print("PSU: Setting %d Vout = %g" % (supNum, volt))
		self.write("VOLTage %f,(@%d)"% (volt, supNum))
	def getOutVolt(self, supNum):
		return float(self.ask("VOLTage? (@%d)"% supNum))
	def getOutCurrent(self, supNum):
		return float(self.ask("CURRent? (@%d)"% supNum))

	# Shortcuts
	def write(self, s):
		if (self.DRY):
			print("DRY-Wr: '%s'" % s)
		else:
			self.psu.write(s)

	def ask(self, s):
		if (self.DRY):
			print("DRY-As: '%s'" % s)
			return '0'
		else:
			return self.psu.ask(s)

	def read(self):
		if (self.DRY):
			print("DRY-Rd: '%s'" % s)
			return '0'
		else:
			return self.psu.read()
			
	def getRealVolt(self, supNum):
		self.write("MEASure:VOLTage? (@%d);*WAI"% supNum)
		return self.read()

	def getDat(self, supNum):
		val = meas();
		#print("V")
		self.write("MEASure:VOLTage? (@%d);*WAI"% supNum)
		val.v=self.read()
		#print("RMS")
		self.write("MEASure:VOLTage:ACDC? (@%d);*WAI"% supNum)
		val.vrms=self.read()
		#print("I")
		self.write("MEASure:CURRent? (@%d);*WAI"% supNum)
		val.i=self.read()
		#print("P")
		if supNum != 1:
			self.write("MEASure:POWer? (@%d);*WAI"% supNum)
			val.p=self.read()
		else:
			val.p=-1
		#print("Done!")
		return val

### Individual Measurements
class meas():
	def __init__(self):
		self.v=False;
		self.vrms=False;
		self.i=False;
		#self.p=False;
		pass
	
	def __repr__(self):
		return('%12sA @ %12sV (%12sVrms)' %
			(EngNumber(self.i,5),
			 EngNumber(self.v,5),
			 EngNumber(self.vrms,5)))

if False:
	print("================")
	setOutVoltMaxALL(1.15)	# Set overvoltage protection limits
	setOutVRangeMinAll()	# set each supply to its lowest voltage range
	setOutIRangeMinAll()	# set each supply to its lowest current range
	setOutILimitAll(0.5e-3) # (TRY to) set current max to 500uA

if False:
	voltSet = 0;
	voltStep = 100e-3;
	setOutOn(supNum)
	while voltSet < 1.0:
		voltSet = voltSet+voltStep;
		setOutVolt(voltSet, supNum)
		setVal = getOutVolt(supNum);
		sleep(0.5)
		x=getDat(supNum);
		print("%4g: %s" % (setVal, x))
		sleep(0.5)
	print("================")

	supNum=2;
	voltSet = 0;
	setOutOn(supNum)
	while voltSet < 1.0:
		voltSet = voltSet+voltStep;
		setOutVolt(voltSet, supNum)
		setVal = getOutVolt(supNum);
		sleep(0.5)
		x=getDat(supNum);
		print("%4g: %s" % (setVal, x))
		sleep(0.5)

	rst()
	print("================")

