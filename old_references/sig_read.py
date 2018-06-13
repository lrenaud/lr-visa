#!/usr/bin/env python3

# sudo -H pip3 install pyvisa-py
import visa
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
from sys import stdout
from engineering_notation import *
from struct import unpack
import numpy as np
import skrf as rf # scikit-rf

MOD_LIST=['QPSK']
MOD_LIST.extend(list(map(lambda x: 'QAM%d' % 2**x, range(4,11))))

class sig_read():
	def __init__(self, rm=None, ip_addr='169.254.219.51', DRY=True, timeout=120):
		self.rm=rm
		self.DRY = DRY
		self.EVMStatsNames = None
		self.EVMStatsUnits = None
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
		# Tie into the USB interface fpr the Generator
		print(self.ask("*IDN?"))
		self.pre_wait()
		self.extra_sleep = -1
	
	######################
	## Reset
	## reset the device (everything)
	def rst(self):
		print("N9030A: Reset called.")
		self.write("*RST")
	def reset(self):
		self.rst()
	def clear(self):
		print("N9030A: clear called.")
		self.write("*CLS")
	def pre_wait(self):
		print("N9030A: configuring OPC")
		self.write("*OPC")
	def wait(self, quiet=False, loud=False):
		if self.extra_sleep > 0:
			if(not quiet):
				print("N9030A: sleeping prior to calling OPC wait.\n" + \
					"      %g seconds" % self.extra_sleep)
			sleep(self.extra_sleep)
		if(not quiet):
			print("N9030A: Waiting for sync.")
		if not self.DRY:
			if self.rm == None:
				while(self.ask("*OPC?") != '1'):
					if(loud):
						print(">>> sleep")
					sleep(10e-3)
			else:
				self.write("*OPC?")
				query=self.read() + '0'
				while(query[0] == '0'):
					if(loud):
						print(">>> sleep")
					sleep(10e-3)
					query=self.read() + '0'
		if(not quiet):
			print("      cleared wait.")
	
	# Shortcuts
	def write(self, s):
		if (self.DRY):
			print("DRY-Wr: '%s'" % s)
		else:
			self.h.write(s)
	
	def ask(self, s):
		if (self.DRY):
			print("DRY-As: '%s'" % s)
			return '0'
		else:
			if self.rm == None:
				return self.h.ask(s)
			else:
				return self.h.query(s)
	
	def read(self):
		if (self.DRY):
			print("DRY-Rd: '%s'" % s)
			return '0'
		else:
			return self.h.read()
	
	######################
	def setMode(self, mode="VSA"):
		self.write(":INST %s;" % mode)

	def setCF(self, frequency_ghz):
		self.write(":FREQ:CENT %gGHz"% frequency_ghz)
	def setSpan(self, span_mhz):
		self.write(":FREQ:SPAN %gMHz"% span_mhz)
	def getCF(self):
		tmp=EngNumber(self.ask(":FREQ:CENT?"))
		tmp.precision=6;
		return tmp
	def getSpan(self):
		tmp=EngNumber(self.ask(":FREQ:SPAN?"))
		tmp.precision=6;
		return tmp

	def runFree(self):
		self.write(":INIT:CONT ON")
	def runSingle(self):
		self.write(":INIT:CONT OFF")
		self.write(":INIT")
	
	def setModulation(self, mod_str, wait=True):
		if not (mod_str in MOD_LIST):
			print("ILLEGAL MODULATION! '%s'\n   using '%s' as a fallback.", \
				mod_str, MOD_LIST[0])
			mod_str=MOD_LIST[0]
		self.write(":DDEMod:MOD %s" % mod_str)
		print("N9030A: set modulation %s" % mod_str)
		if wait:
			print("           waiting...", end='')
			stdout.flush()
			self.wait(quiet=True)
			print(" ready!")
	def getModulation(self):
		return self.ask(":DDEMod:MOD?")[:-1]
	
	def setDataRate(self, rate_hz, wait=True):
		if EngNumber != type(rate_hz):
			rate_hz=EngNumber(rate_hz)
			rate_hz.precision=6;
		self.write(":DDEMod:SRATe %sHz" % rate_hz)
		print("N9030A: set rate %sHz" % rate_hz, end='')
		if wait:
			print("      waiting...", end='')
			stdout.flush()
			self.wait(quiet=True)
			print(" ready!")
		else:
			print("")
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
		
	def getEVMStats(self, asDict=True):
		self.wait(quiet=True)
		data=self.ask(":CALC:DDEM:DATA4:TABL?").replace('\n','').split(',')
		if self.EVMStatsNames == None:
			self.getEVMStatsName()
		if self.EVMStatsUnits == None:
			self.getEVMStatsUnits()
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
	def getEVMStatsName(self):
		stats_string=self.ask(":CALC:DDEM:DATA4:TABL:NAM?")
		self.EVMStatsNames=stats_string.replace('"','').strip('\n').split(',')
	def getEVMStatsUnits(self):
		stats_string=self.ask(":CALC:DDEM:DATA4:TABL:UNIT?")
		self.EVMStatsUnits=stats_string.replace('"','').strip('\n').split(',')
		
	def runSamples(self, nSamples=16):
		self.runSingle()
		self.wait(quiet=True)
		data_tmp, data_units = self.getEVMStats()
		data = {}
		for key in data_tmp.keys():
			data[key]=[data_tmp[key]]
		for i in range(nSamples-1):
			self.runSingle()
			self.wait(quiet=True)			
			data_tmp, data_units = self.getEVMStats()
			#print(data_tmp)
			for key in data_tmp.keys():
				data[key].append(data_tmp[key])
		data['UNITS'] = data_units;
		return data

if __name__ == "__main__":
	h=sig_read(DRY=False)
	h.runFree()
