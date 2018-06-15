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
from struct import unpack

import numpy as np
import skrf as rf # scikit-rf

###############
rf.stylely()
import matplotlib.pyplot as plt
###############

class pnaPNAX():
	# This method is used to startup a new PNAx connection.
	#def __init__(self, DRY=True, timeout=120):
	# TODO Select an IP for the PNAX and insert it here as the default.
	# all of the other hardware follows this template, so please only change
	# the XX in the example below.
	def __init__(self, rm=None, ip_addr='169.254.219.xx', DRY=True, timeout=120):
		self.DRY = DRY
		self.rm=rm
		self.extra_sleep = -1
		# OLD USB CODE
		if False:
			if (self.DRY==False):
				self.h=usbtmc.Instrument(0x0957, 0x0118)
				self.h.timeout = timeout
		else:
			if self.rm == None:
				self.rm=visa.ResourceManager('@py')
			self.TCPIP_STR='TCPIP0::%s::inst0::INSTR' % ip_addr
			if (self.DRY==False):
				self.h=self.rm.open_resource(self.TCPIP_STR)
				self.h.timeout = timeout
		# Tie into the USB interface for the PNA-X
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
			if tmpString[-1] == '\n' and strip:
				tmpString = tmpString[:-1]
			return tmpString
	# The normal "read" call
	def readNL(self):
		return self.read(strip=False)

	###########################################################################
	# Unique Class Methods
	###########################################################################

	def config_fswp(self, center_ghz, span_ghz, df_ghz, pwr=-20):
		lower = center_ghz - span_ghz/2;
		upper = center_ghz + span_ghz/2;
		steps = round(span_ghz/df_ghz) + 1;
		# Verify we will hit center exactly
		(steps-1/2)
		self.write("SENS:SWE:TYPE LIN;*WAI") # set to linear frequency sweep
		self.write("SENS:FREQ:STAR %ge9;*WAI"% lower) # Start frequency
		self.write("SENS:FREQ:STOP %ge9;*WAI"% upper) # Stop frequency
		self.write("SENS:SWE:POIN %d"% steps) # Set number of steps
		self.write("SOUR:POW:LEV %d;*WAI"% pwr) # set to -30dBm input power
		self.write("FORMAT REAL,64") # use peak precision
		print(self.ask("*OPC?"))

	def getPtsSwpLen(self):
		return(self.ask("SENS:SWE:POIN?"))
	def config_s2p_meas(self):
		cur_test=self.pna.ask("CALC:PAR:CAT:EXT?")
		cur_tests=cur_test.replace('"','').split(",")
		# remove existing tests
		for i in range(round(len(cur_tests)/2)):
			self.write("CALC:PAR:DEL '%s'"% cur_tests[i*2])
		# If these exist they will
		self.write("CALC:PAR:DEF:EXT 'CH1_S11_1',S11")
		self.write("CALC:FORM REAL")
		self.write("CALC:PAR:DEF:EXT 'CH1_S12_2',S12")
		self.write("CALC:FORM REAL")
		self.write("CALC:PAR:DEF:EXT 'CH1_S21_3',S21")
		self.write("CALC:FORM REAL")
		self.write("CALC:PAR:DEF:EXT 'CH1_S22_4',S22")
		self.write("CALC:FORM REAL")
		
		#self.write("CALC:PAR:SEL 'CH1_S11_1','CH1_S11_1','CH1_S11_1','CH1_S11_1',")
	
	def config_s2p_disp(self):
		self.write("DISP:WIND:TRAC1:FEED 'CH1_S11_1'")
		self.write("DISP:WIND:TRAC2:FEED 'CH1_S12_2'")
		self.write("DISP:WIND:TRAC3:FEED 'CH1_S21_3'")
		self.write("DISP:WIND:TRAC4:FEED 'CH1_S22_4'")
	
	def avgEnable(self, npts=10):
		self.write("SENS:AVER ON")#set average ON
		self.write("SENS:AVER:MODE POIN")#set averaging to point mode
		self.write("SENS:AVER:COUN %d" % npts)#set the number of average to 10
	def avgDisable(self):
		self.write("SENS:AVER OFF")#set average OFF

	def meas_cont(self):
		print("PNAX: Measuring continious")
		self.write("INIT:CONT ON")
	def meas_single(self):
		self.write("INIT:CONT OFF")
		self.write("INIT:IMM;*WAI")
		print("PNAX: Measuring single. LOCKING....")
		self.wait(quiet=True)
		print("      Lock cleared.")
				
	def meas_s2p(self):
		#global s2p_pre, s2p, freq
		self.write("CALC:DATA:SNP:PORTs? '1,2'")
		raw_dat_pre=self.pna.read_raw()
		#f = open('tmp_pna.bin','bw+')
		#f.write(raw_dat_pre)
		#f.close()
		# first cutout the header
		digits			= int(raw_dat_pre[1:2])
		freq_pts		= int(self.ask("SENS:SWE:POIN?"))
		# 8 byte double * frequency pts * ((channel I + channel Q )*n + freq)
		#data_points		= freq_pts * (1+2*channel_count);
		data_bytes		= int(raw_dat_pre[2:(2+digits)])
		data_points		= int(data_bytes/8);
		#print(data_points, freq_pts)
		raw_dat			= raw_dat_pre[(2+digits):-1]

		# next convert the data to floating point
		# we instruct python to pull the number of data points (i.e. 8 byte
		# chunks) decoded as double precision floating point values.
		decoded_floats = unpack('>%dd' % data_points, raw_dat)
		# We expect to have frequency lists, followed bi R/I lists for each
		# channel we measure. So 1 + 2*C data streams.
		s2p = np.zeros(freq_pts)
		s2p_pre = []
		for i in range(1+2*4):
			if (i == 0):
				freq = np.array(decoded_floats[0:freq_pts])
			else:
				s2p_pre.append(decoded_floats[i*freq_pts:(i+1)*freq_pts])
		# Finally, generate the real/imaginary data for python to handle.
		# There are RF python libraries that will automatically create touch-
		# stone SnP files from the data if we want.
		s2p_pre = np.array(s2p_pre)
		for i in range(4):
			s2p = np.column_stack(\
				(\
					s2p, \
					np.array(s2p_pre[i*2]+ np.multiply(1j,s2p_pre[(i*2)+1]))\
				))
		# remove the padding zeros
		s2p = s2p[:,1:].reshape(freq_pts,2,2);
		
		# now generate the network paramater file
		n=rf.Network(frequency=freq, f_unit='Hz', s=s2p, z0=50)
		return n
###############################################################################
# END OF CLASS
###############################################################################


# Run this ONLY if we are called directly rather than imported
if __name__ == "__main__":
	h = pnaPNAX(DRY=False)
	h.config_fswp(28, 8, 0.001)
	h.config_s2p_meas()
	h.config_s2p_disp()
	h.meas_single()
	n=h.meas_s2p()

	fig, axarr = plt.subplots(2,1, sharex=True, figsize=(6,7))
	n.plot_s_db(ax=axarr[0])
	#axarr[0].title='Test S-Params'
	n.plot_s_deg_unwrap(ax=axarr[1])
	fig.show()
	#fig.savefig('test.png')
	#fig.savefig('test.pdf')

