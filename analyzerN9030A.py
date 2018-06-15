#!/usr/bin/env python3
###############################################################################
###############################################################################
# KNOWN BUGS and TODO:
###############################################################################
# TODO: write this list
# 1. Much of the code can be refactored int a generic superclass for VISA
# 		instruments. There are other projects that already do this to some
#		extent, but I haven't really dug into them in full. This would also
#		ease porting the library to other PSUs and configurations
# 2. Make the library properly USB/Ethernet agnostic.
# 3. Ensure we actually provide a complete set of functionality for the system.
#		Currently we have no unit testing or anything of the sort.
# 4. Standardize measurement vernacular across classes.
###############################################################################
# KNOWN MISSING FEATURES, TODO:
# TODO: write this list
#	IMPORTANT: Verify the .wait() command is actually working!
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

# Used if we end up reading in binary packed data.
# This was currently something that I only did in the PNA-X.
#from struct import unpack

# For mangling the data.
import numpy as np
import skrf as rf # scikit-rf

MOD_LIST=['QPSK']
MOD_LIST.extend(list(map(lambda x: 'QAM%d' % 2**x, range(4,11))))

###############################################################################
class analyzerN9030A():
	def __init__(self, rm=None, ip_addr='169.254.219.51', DRY=True, timeout=120):
		self.DRY = DRY
		self.rm=rm
		self.extra_sleep = -1
		# OLD USB CODE
		if False:
			if (self.DRY==False):
				self.h=usbtmc.Instrument(0x0957, 0x0d0b)
				self.h.timeout = timeout
		else:
			if self.rm == None:
				self.rm=visa.ResourceManager('@py')
			self.TCPIP_STR='TCPIP0::%s::inst0::INSTR' % ip_addr
			if (self.DRY==False):
				self.h=self.rm.open_resource(self.TCPIP_STR)
				self.h.timeout = timeout
		# Tie into the USB interface for the Generator
		self.msg(self.ask("*IDN?"))
		self.pre_wait()
		self.wait()
		self.EVMStatsUnits=None # These probably shouldn't be predefined
		self.EVMStatsNames=None # These probably shouldn't be predefined
	
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
			if self.rm == None:
				while(self.ask("*OPC?") != '1'):
					if(loud):
						self.msg(">>> sleep")
					sleep(10e-3)
			else:
				self.write("*OPC?")
				query=self.read() + '0'
				while(query[0] == '0'):
					if(loud):
						self.msg(">>> sleep")
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
			if tmpString[-1] == '\n' and strip:
				tmpString = tmpString[:-1]
			return tmpString
	# The normal "read" call
	def readNL(self):
		return self.read(strip=False)

	###########################################################################
	# Unique Class Methods
	###########################################################################
	
	######################
	def setMode(self, mode="VSA"):
		self.write(":INST %s;" % mode)

	# Getting and setting of center frequency and frequency span
	def setCF(self, frequency_hz):
		self.write(":FREQ:CENT %gHz"% float(frequency_hz))
	def setCF_ghz(self, frequency_ghz):
		self.write(":FREQ:CENT %gGHz"% float(frequency_ghz))
	def setSpan(self, span_hz):
		self.write(":FREQ:SPAN %gHz"% float(span_hz))
	def setSpan_mhz(self, span_mhz):
		self.write(":FREQ:SPAN %gMHz"% float(span_mhz))
	def getCF(self):
		return EngNumber(self.ask(":FREQ:CENT?"), 6)
	def getSpan(self):
		return EngNumber(self.ask(":FREQ:SPAN?"), 6)

	# Continuously sample data
	def runFree(self):
		self.write(":INIT:CONT ON")
	# Run a single measurement
	def runSingle(self):
		self.write(":INIT:CONT OFF")
		self.write(":INIT")
	
	def setModulation(self, mod_str, wait=True):
		if not (mod_str in MOD_LIST):
			self.msg("ILLEGAL MODULATION! '%s'\n   using '%s' as a fallback.", \
				mod_str, MOD_LIST[0])
			mod_str=MOD_LIST[0]
		self.write(":DDEMod:MOD %s" % mod_str)
		self.msg("set modulation %s" % mod_str)
		if wait:
			self.msg("           waiting...", end='', flush=True)
			self.wait(quiet=True)
			self.msg(" ready!")
	def getModulation(self):
		return self.ask(":DDEMod:MOD?")[:-1]
	
	def setDataRate(self, rate_hz, wait=True):
		if EngNumber != type(rate_hz):
			rate_hz=EngNumber(rate_hz)
			rate_hz.precision=6;
		self.write(":DDEMod:SRATe %sHz" % rate_hz)
		self.msg("set rate %sHz" % rate_hz, end='')
		if wait:
			self.msg("      waiting...", end='', flush=True)
			self.wait(quiet=True)
			self.msg(" ready!")
		else:
			self.msg("")
	def getDataRate(self):
		return self.ask(":DDEMod:SRATe?")[:-1]
	
	######################
	def getDataChannel(self, channel=1):
		self.wait(quiet=True)
		tmp = self.ask(":CALC:DDEM:DATA%d? X" % channel).strip('\n').split(',')
		x=list(map(float,tmp))
		tmp = self.ask(":CALC:DDEM:DATA%d? Y" % channel).strip('\n').split(',')
		y=list(map(float,tmp))
		return (x,y)
		
	def EVM_getStats(self, asDict=True):
		self.wait(quiet=True)
		data=self.ask(":CALC:DDEM:DATA4:TABL?").replace('\n','').split(',')
		if self.EVMStatsNames == None:
			self.EVM_getStatsName()
		if self.EVMStatsUnits == None:
			self.EVM_getStatsUnits()
		keepPts=[]
		for iPt,vPt in enumerate(data):
			if (vPt != '9.91E+37'):
				keepPts.append(iPt)
		if asDict == True:
			dat_set = {}
			data_units = {}
		else:
			dat_set = []

		for iPt in keepPts:
			name = self.EVMStatsNames[iPt]
			if name[-3:] == 'Sym':
				value = int(float(data[iPt]))
			else:
				value = float(data[iPt])
			if asDict:
				dat_set[name]=value
				data_units[name]=self.EVMStatsUnits[iPt]
			else:
				dat_set.append(value)
		return (dat_set,data_units)
	def EVM_getStatsName(self):
		stats_string=self.ask(":CALC:DDEM:DATA4:TABL:NAM?")
		self.EVMStatsNames=stats_string.replace('"','').strip('\n').split(',')
	def EVM_getStatsUnits(self):
		stats_string=self.ask(":CALC:DDEM:DATA4:TABL:UNIT?")
		self.EVMStatsUnits=stats_string.replace('"','').strip('\n').split(',')
		
	def EVM_runSamples(self, nSamples=16):
		self.runSingle()
		self.wait(quiet=True)
		data_tmp, data_units = self.EVM_getStats()
		data = {}
		for key in data_tmp.keys():
			data[key]=[data_tmp[key]]
		for i in range(nSamples-1):
			self.runSingle()
			self.wait(quiet=True)			
			data_tmp, data_units = self.EVM_getStats()
			#print(data_tmp)
			for key in data_tmp.keys():
				data[key].append(data_tmp[key])
		data['UNITS'] = data_units;
		return data
###############################################################################
# END OF CLASS
###############################################################################

if __name__ == "__main__":
	h=analyzerN9030A(DRY=False)
	h.runFree()
