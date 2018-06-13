#!/usr/bin/env python3

#import visa as v
import usbtmc

from time import sleep
#from engineering_notation import *
from struct import unpack
import numpy as np
import skrf as rf # scikit-rf

###############
rf.stylely()
import matplotlib.pyplot as plt
###############

class pna1():
	# This method is used to startup a new PNAx connection. It 
	def __init__(self, DRY=True, timeout=120):
		self.DRY = DRY;
		if (self.DRY==False):
			self.pna=usbtmc.Instrument(0x0957, 0x0118)
			self.pna.timeout = timeout
		# Tie into the USB interface fpr the PNA-X
		print(self.ask("*IDN?"))
		self.pre_wait()
		self.extra_sleep = -1
	
	######################
	## Reset
	## reset the device (everything)
	def rst(self):
		print("PNAX: Reset called.")
		self.write("*RST")
	def reset(self):
		self.rst()
	def clear(self):
		print("PNAX: clear called.")
		self.write("*CLS")
	def pre_wait(self):
		print("PNAX: configuring OPC")
		self.write("*OPC")
	def wait(self, quiet=False, loud=False):
		if self.extra_sleep > 0:
			if(not quiet):
				print("PNAX: sleeping prior to calling OPC wait.\n" + \
					"      %g seconds" % self.extra_sleep)
			sleep(self.extra_sleep)
		if(not quiet):
			print("PNAX: Waiting for sync.")
		if not self.DRY:
			while(self.ask("*OPC?") == '0'):
				if(loud):
					print(">>> sleep")
				sleep(10e-3)
		if(not quiet):
			print("      cleared wait.")

	# Shortcuts
	def write(self, s):
		if (self.DRY):
			print("DRY-Wr: '%s'" % s)
		else:
			self.pna.write(s)

	def ask(self, s):
		if (self.DRY):
			print("DRY-As: '%s'" % s)
			return '0'
		else:
			return self.pna.ask(s)

	def read(self):
		if (self.DRY):
			print("DRY-Rd: '%s'" % s)
			return '0'
		else:
			return self.pna.read()
			
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

if __name__ == "__main__":
	pna = pna1(DRY=False)
	pna.config_fswp(28, 8, 0.001)
	pna.config_s2p_meas()
	pna.config_s2p_disp()
	pna.meas_single()
	n=pna.meas_s2p()

	fig, axarr = plt.subplots(2,1, sharex=True, figsize=(6,7))
	n.plot_s_db(ax=axarr[0])
	#axarr[0].title='Test S-Params'
	n.plot_s_deg_unwrap(ax=axarr[1])
	fig.show()
	fig.savefig('test.png')
	fig.savefig('test.pdf')

