#!/usr/bin/env python3
###############################################################################
# A simple tool that assumes a device that accepts a binary 8-bit digit on a
# serial interface. It then tries to set that digit to 8 output pins, and
# reads the response of 8 other pins back to the tool.
###############################################################################
# Linux Dependencies
#######################
# sudo -H pip3 install pyserial

import serial
from time import sleep, time

class ourDumbDigital():
	def __init__(self, SERIAL_PORT = '/dev/ttyUSB0', SERIAL_BAUDRATE = 115200,\
		auto_open = True):
		self.htty = serial.Serial(SERIAL_PORT);
		self.htty.baudrate = SERIAL_BAUDRATE
		if auto_open:
			self.openPort()

	@property
	def port(self):
		return self.htty.port

	def openPort(self):
		if not self.htty.is_open:
			self.htty.open()

	def startupWait(self):
		self.openPort()
		start_time = time()
		while(self.htty.read_all() == b''):
			sleep(10e-3)
		end_time = time()
		print(" %f seconds." % (end_time - start_time), end='')
		self.setCode(0x00, flushOut=True)
	
	def setCode(self, code:int=0, quiet = True, flushOut=False):
		trunk_word = bytes([code & 2**(8)-1]) # limit to 8-bits
		self.htty.read_all()
		self.htty.write(trunk_word)
		self.htty.flush()
		# Now read the set and read codes
		while(self.htty.in_waiting == 0):
			sleep(1e-3)
		if flushOut:
			self.htty.read_all()
			return -1
		else:
			RESP1 = self.htty.readline()
			RESP1int = int(RESP1.decode().strip('\n').split(' ')[-1], 16)
			RESP2 = self.htty.readline()
			RESP2int = int(RESP2.decode().strip('\n').split(' ')[-1], 16)
			if not quiet:
				print('Serial Control: SET 0x%02X, GOT 0x%02X' % (RESP1int, RESP2int))
			return RESP2int

if __name__ == "__main__":
	print("Starting...")
	h = ourDumbDigital();
	# Wait for TTY to open by using a blocking call
	print("Waiting for serial device '%s'..." % h.port, end='', flush=True)
	h.startupWait()
	print(" done!")
	sleep(100e-3)

	for A in range(256):
		dat = h.htty.read_all()
		if dat != b'':
			print(dat.decode())
		sleep(1e-3)
		print("TRY: 0x%02X... " % (A), end='', flush=True)
		print("→ 0x%02X" % h.setCode(A, quiet=True))

