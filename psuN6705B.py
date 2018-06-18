#!/usr/bin/env python3
###############################################################################
###############################################################################
# KNOWN BUGS and TODO:
###############################################################################
# 1. Much of the code can be refactored int a generic superclass for VISA
# 		instruments. There are other projects that already do this to some
#		extent, but I haven't really dug into them in full. This would also
#		ease porting the library to other PSUs and configurations
# 2. Make the library properly USB/Ethernet agnostic.
# 3. Ensure we actually provide a complete set of functionality for the system.
#		Currently we have no unit testing or anything of the sort.
# 4. Standardize measurement vernacular across classes.
# 5. Figure out why the power measurement of PSU#1 on WSU's equipment always
#		hangs. It's a different module than in #2-#4, but it's not clear if
#		there is a way to pragmatically check for the functionality to
#		measure power directly rather than current/voltage.
###############################################################################
# KNOWN MISSING FEATURES, TODO:
#	output grouping
#	output coupling
#	output logging
#	slew rate control
#	delay controls
#	data logger
#	scope view
#	view controlling
#	usb interfaces
#	advanced protection
###############################################################################

# Linux Dependencies (For the LAN Mode)
#######################
# sudo -H pip3 install pyvisa-py 
# sudo -H pip3 install engineering-notation
#######################
# Now you're set to go!


# Linux Dependencies (For the old USB Mode)
#######################
# sudo -H pip3 install python-usbtmc pyusb
# sudo -H pip3 install numpy scikit-rf engineering-notation
# under Linux, create a usbtmc group, and add your user to that group
## i.e. $ sudo chmod groupadd usbtmc
#       $ sudo usermod -aG usbtmc <your username>
# then logout and login to make the changes take effect.
#
# now add the following udev rule to a file (example name shown)
## /etc/udev/rules.d/usbtmc.rules
# SUBSYSTEMS=="usb", ACTION=="add", ATTRS{idVendor}=="0957", GROUP="usbtmc", MODE="0660"
#######################
# Now you're set to go!

import visa	# For LAN and USB, but we only use for the LAN mode right now.
#import usbtmc
from time import sleep
from engineering_notation import *

# For JSON dumping PSU_Samples
import json

###############################################################################
class psuN6705B():
	MAX_SUP_GLOBAL = 4
	def __init__(self, rm=None, ip_addr='169.254.219.40', DRY=True, timeout=120):
		self.DRY = DRY
		self.rm=rm
		self.extra_sleep = -1
		# OLD USB CODE
		if False:
			if (self.DRY==False):
				self.h=usbtmc.Instrument(0x0957, 0x0f07)
				self.h.timeout = timeout
		else:
			if self.rm == None:
				self.rm=visa.ResourceManager('@py')
			self.TCPIP_STR='TCPIP0::%s::inst0::INSTR' % ip_addr
			if (self.DRY==False):
				self.h=self.rm.open_resource(self.TCPIP_STR)
				self.h.timeout = timeout
		# Tie into the USB interface for the N6705B
		self.msg(self.ask("*IDN?"))
		self.pre_wait()
		self.wait()
	
	###########################################################################
	## Reset
	## reset the device (everything)
	def rst(self):
		self.msg("Reset called.")
		self.write("*RST")
	def reset(self):
		self.rst()
	def clear(self):
		self.msg("clear called.")
		self.write("*CLS")
	# Setup the system to support OPC wait for operations to finish
	def pre_wait(self):
		self.msg("configuring OPC")
		self.write("*OPC")
	# Actually do the wait. if quiet this is silent.
	def wait(self, quiet=False, loud=False):
		if self.extra_sleep > 0:
			if(not quiet):
				self.msg("Pre-sleep for extra %g seconds" % self.extra_sleep)
			sleep(self.extra_sleep)
		if(not quiet):
			self.msg("Waiting for sync... ", end='', flush=True)
		if not self.DRY:
			# rm is a simple test to see if we're in VISA mode
			self.write("*OPC?")
			query=self.read() + '0'
			while(query[0] == '0'):
				if(loud):
					print(">>> sleep")
				sleep(10e-3)
				query=self.read() + '0'
		if(not quiet):
			self.msg_plain(" done!")
	def msg(self, message, end='\n'):
		# remove trailing newlines as present in most VISA responses.
		if message[-1] == '\n':
			message=message[:-1]
		annotated_message = '%s: %s' % (self.__class__.__name__, message)
		print(annotated_message, end=end)
	def msg_plain(self, message, end='\n'):
		# remove trailing newlines as present in most VISA responses.
		if message[-1] == '\n':
			message=message[:-1]
		print(message, end=end)

	###########################################################################
	# Data handling helper functions
	def arraySplitMap(message, engNumber=True):
		# Spit a comma separated array and map the values as floats or EngNumbers.
		dat_arr=message.split(',')
		if engNumber:
			data_mapping=map(lambda x: EngNumber(x, 6), dat_arr)
		else:
			data_mapping=map(float, dat_arr)
		return list(data_mapping)

	###########################################################################
	# Shortcuts to the slave object
	def write(self, s):
		if (self.DRY):
			self.msg("DRY_WRITE: '%s'" % s)
		else:
			self.h.write(s)
	
	def ask(self, s):
		return self.query(s)
	def query(self, s, strip=True):
		if (self.DRY):
			self.msg("DRY_ASK__: '%s'" % s)
			return '0'
		else:
			tmpString = self.h.query(s)
			if tmpString[-1] == '\n' and strip:
				tmpString = tmpString[:-1]
			return tmpString
	def queryNL(self, s):
		return self.query(s, strip=False)

	# a read that strips trailing newlines.
	def read(self, strip=True):
		if (self.DRY):
			self.msg("DRY_READ_:")
			return '0'
		else:
			tmpString = self.h.read()
			if strip and len(tmpString) > 0:
				if tmpString[-1] == '\n':
					tmpString = tmpString[:-1]
			return tmpString
	# The normal "read" call
	def readNL(self):
		return self.read(strip=False)

	###########################################################################
	# Unique Class Methods
	###########################################################################

	## Output Enable/Disable
	def setOutToggle(self, supNum):
		if self.getOutState(supNum):
			self.setOutOff(supNum)
		else:
			self.setOutOn(supNum)
			
	# Fetch output on/off
	def getEnabled(self, supNum):
		return bool(int(self.ask("OUTPut? (@%d)"% supNum)))
	def getEnabledAll(self, maxSup = MAX_SUP_GLOBAL):
		enabledResponses=self.ask("OUTPut? (@1:%d)"% maxSup).split(',')
		enabledResponseInts = list(map(int,enabledResponses))
		return list(map(bool,enabledResponseInts))
	def getOutState(self, supNum):
		return self.getEnabled(supNum)

	def enableSupply(self, supNum):
		self.write("OUTPut ON,(@%d)"% supNum)
	def enableSupplyAll(self, maxSup = MAX_SUP_GLOBAL):
		self.write("OUTPut ON,(@1:%d)"% maxSup)
	def setOutOn(self, supNum):
		self.enableSupply(supNum)

	def disableSupply(self, supNum):
		self.write("OUTPut OFF,(@%d)"% supNum)
	def disableSupplyAll(self, maxSup = MAX_SUP_GLOBAL):
		self.write("OUTPut OFF,(@1:%d)"% maxSup)
	def setOutOff(self, supNum):
		self.disableSupply(supNum)
		
	###########################################################################
	## Control Maximum Current/Voltage Limits
	# Voltage limits
	def getOutVoltMax(self, supNum):
		return EngNumber(self.ask("VOLTage:PROT? (@%d)"% (supNum)))
	def getOutVoltMaxAll(self, maxSup = MAX_SUP_GLOBAL):
		retString = self.ask("VOLTage:PROT? (@1:%d)"% (maxSup))
		return psuN6705B.arraySplitMap(retString, engNumber=True)
		
	def setOutVoltMax(self, volt, supNum):
		self.msg("Setting %d VMAX = %g" % (supNum, volt))
		self.write("VOLTage:PROT %f,(@%d)"% (volt, supNum))

	def setOutVoltMaxAll(self, volt, maxSup = MAX_SUP_GLOBAL):
		self.msg("Setting all VMAX = %g" % volt)
		self.write("VOLTage:PROT %f,(@1:%d)"% (volt, maxSup))
	
	# Current limits
	def getOutILimit(self, supNum):
		return EngNumber(self.ask("CURRent? (@%d)"% (supNum)))
	def getOutILimitAll(self, maxSup = MAX_SUP_GLOBAL):
		retString = self.ask("CURRent? (@1:%d)"% (maxSup))
		return psuN6705B.arraySplitMap(retString, engNumber=True)

	def setOutILimit(self, imax, supNum):
		self.msg("Setting %d IMAX = %g" % (supNum, imax))
		self.write("CURRent %f,(@%d)"% (imax, supNum))

	def setOutILimitAll(self, imax, maxSup = MAX_SUP_GLOBAL):
		self.msg("Setting all IMAX = %g" % (imax))
		self.write("CURRent %f,(@1:%d)"% (imax, maxSup))
		
	###########################################################################
	## Fetch and set ranges to minimums
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


	###########################################################################
	# Core setting
	def setOutVolt(self, volt, supNum):
		self.msg("Setting %d Vout = %g" % (supNum, volt))
		self.write("VOLTage %f,(@%d)"% (float(volt), supNum))
	def getOutVolt(self, supNum, engNumber=True):
		tmpRet = self.ask("VOLTage? (@%d)"% supNum)
		if engNumber: tmpRet=EngNumber(tmpRet)
		else: tmpRet=float(tmpRet)
		return tmpRet
	def getOutCurrent(self, supNum, engNumber=True):
		tmpRet = self.ask("CURRent? (@%d)"% supNum)
		if engNumber: tmpRet=EngNumber(tmpRet)
		else: tmpRet=float(tmpRet)
		return tmpRet

	###########################################################################
	# Measurement of the PSU
	def getRealVolt(self, supNum):
		self.write("MEASure:VOLTage? (@%d);*WAI"% supNum)
		return self.read()

	def getDat(self, supNum, doPower=False):
		val = PSU_Sample();
		self.write("MEASure:VOLTage? (@%d);*WAI"% supNum)
		v=self.read()
		self.write("MEASure:VOLTage:ACDC? (@%d);*WAI"% supNum)
		vrms=self.read()
		self.write("MEASure:CURRent? (@%d);*WAI"% supNum)
		i=self.read()
		if doPower:
			self.write("MEASure:POWer? (@%d);*WAI"% supNum)
			p=self.read()
		else:
			p=-1
		val.setAll(v=float(v),vrms=float(vrms),i=float(i),p=float(p))
		return val

	def getDatAll(self, maxSup = MAX_SUP_GLOBAL):
		vals = list(map(lambda _: PSU_Sample(),range(maxSup)));
		self.write("MEASure:VOLTage? (@1:%d);*WAI"% maxSup)
		v_tmp=list(map(float,self.read().split(',')))
		self.write("MEASure:VOLTage:ACDC? (@1:%d);*WAI"% maxSup)
		vrms_tmp=list(map(float,self.read().split(',')))
		self.write("MEASure:CURRent? (@1:%d);*WAI"% maxSup)
		i_tmp=list(map(float,self.read().split(',')))
		
		for ind in range(maxSup):
			vals[ind].setAll(	v=v_tmp[ind],\
								vrms=vrms_tmp[ind],\
								i=i_tmp[ind])
		return vals
###############################################################################
# END OF CLASS
###############################################################################
	
### Individual Measurements
class PSU_Sample():
	def __init__(self):
		self.v=False;
		self.vrms=False;
		self.i=False;
		self.p=False;
		pass
	def setAll(self, v=False,vrms=False,i=False,p=False):
		if v != False:
			self.v=v;
		if vrms != False:
			self.vrms=vrms;
		if i != False:
			self.i=i;
		if p != False:
			self.p=p;
	
	def __repr__(self):
		if type(self.i) in [int, float]:
			val_i = EngNumber(self.i,5)
		else:
			val_i = 'Unknown'
		if type(self.v) in [int, float]:
			val_v = EngNumber(self.v,5)
		else:
			val_v = 'Unknown'
		return('%12sV @ %12sA' % (val_v, val_i))
###############################################################################
# END OF CLASS
###############################################################################

# Run this ONLY if we are called directly rather than imported
if __name__ == "__main__":
	h=psuN6705B(DRY=False)
