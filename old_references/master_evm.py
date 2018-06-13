#!/usr/bin/env python3

from time import sleep, strftime, time  # to generate dates for save files
from engineering_notation import *
from struct import unpack
import numpy as np
import skrf as rf # scikit-rf

from os import path, makedirs
import bz2, json, io
import tarfile as tar

import sig_read as READc
import sig_gen as GENc

import matplotlib.pyplot as plt

freq_steps = [100e3, 1e6, 5e6, 10e6];
#freq_steps = [1e6, 5e6, 10e6];
#freq_steps = [100e3, 1e6, 5e6, 8e6, 10e6];
BP_min = 0;
BP_max = 0;

MOD_LIST=['QPSK']
MOD_LIST.extend(list(map(lambda x: 'QAM%d' % 2**x, range(4,9))))
#			QPSK	16		32		64		128		256
PWR_MIN=[	-70,	-66,	-62,	-58,	-56,	-54]
PWR_MIN=[	-70,	-65,	-61,	-58,	-55,	-52]
print("=============================================")
print("=============================================")
print("== HARD RANGE OVERRIDE SETTINGS ARE IN USE ==")
print("=============================================")
print("=============================================")
PWR_MAX=13

RATE_RATIO=np.floor(10*np.log10(np.array(freq_steps)/100e3))
POWER_MAX=10;
POWER_STEPS=50;

def setModGlobal(modulation='QAM64'):
	rh.setModulation(modulation)
	gh.setModulation(modulation)
	readMod=rh.getModulation()
	genMod=gh.getModulation()
	print("Modulation: %s==%s (%s)" % \
		(readMod, genMod, str(readMod==genMod)))
		
def setRateGlobal(rate=EngNumber('1M')):
	rh.setDataRate(rate)
	gh.setDataRate(rate)
	readRate=EngNumber(rh.getDataRate())
	readRate.precision=6;
	genRate=EngNumber(gh.getDataRate())
	genRate.precision=6;
	print("Modulation: %s==%s (%s)" % \
		(readRate, genRate, str(readRate==genRate)))

def testMkDir(path_loc):
	if not path.exists(path_loc):
		makedirs(path_loc)

def runAllSweeps(enabled = False, dontRun100=False):
	saveDirTop='EVMDat-2018-06-12-control'
	testMkDir(saveDirTop)
	i_run=0;
	for iSrate,nSrate in enumerate(freq_steps):
		if nSrate != 5e6: continue
		if nSrate == 100e3 and dontRun100: continue
		if nSrate != 100e3 and not dontRun100: continue
		#if nSrate == 8e6: continue
		eSrate=EngNumber(nSrate)
		saveDirLocal=saveDirTop + '/%d-%ssps' % (iSrate,eSrate)
		testMkDir(saveDirLocal)
		if enabled:
			setRateGlobal(eSrate)
			rh.setSpan(10)
		#print("%ssps" % eSrate)
		# Sweep Modulation
		for iMod,sMod in enumerate(MOD_LIST):
			print(sMod)
			#if nSrate == 1e6 and sMod != 'QAM256': continue
			if enabled: setModGlobal(sMod)
			#print('\t#%d, %s' % (iMod, sMod))
			PWR_LIST=[-30, -20, 0] #TODO: COMPUTE POWER LEVELS FOR THIS MODE <======
			START_POWER=PWR_MIN[iMod] +RATE_RATIO[iSrate]
			PWR_LIST=np.arange(START_POWER,min(START_POWER+POWER_STEPS,10)+1)
			PWR_LIST=np.arange(-10,PWR_MAX+1)
			if False:
				if (START_POWER < -10):
					PWR_LIST_PREFIX = np.arange(START_POWER,-10,2)
					PWR_LIST=np.append(PWR_LIST_PREFIX,PWR_LIST)
			else:
				print("=============================================")
				print("=============================================")
				print("== HARD RANGE OVERRIDE SETTINGS ARE IN USE ==")
				print("=============================================")
				print("=============================================")
				PWR_LIST=np.append(	np.arange(-10,3),\
									np.arange(3,20+0.5,0.5)) # everyone needs this
				# NEW FOR CONTROL DATA
				PWR_LIST=np.arange(-10,20+2,2)
			#print(min(PWR_LIST),max(PWR_LIST))
			#continue
			localTarball = saveDirLocal + ('/%d-%s_source.tar.bz2' % (iMod, sMod))
			fh=tar.open(localTarball, 'w:bz2')
			info_master_data = fh.tarinfo(name=('%d-%s_master.json' % (iMod, sMod)))
			RESULTS={}
			for iPwr,sPwr in enumerate(PWR_LIST): # Sweep Power
				#print('\t\t%5g dBm' % sPwr)
				i_run = i_run + 1;
				runName = '%d-%s_iR%d_R%s_P%+03d' % \
					(iMod, sMod, iSrate, eSrate, sPwr)
				print(strftime("{%Y-%d-%m %H:%M:%S} "), ("%23s   " % runName), \
					"[ %4d ]        %d/%d %d/%d %2d/%2d" % (i_run, \
					iSrate+1, len(freq_steps), \
					iMod+1, len(MOD_LIST), \
					iPwr+1, len(PWR_LIST)))
				if enabled:
					gh.setPower(sPwr) # Set TX power
					rh.wait(quiet=True);gh.wait(quiet=True)
					rh.runSingle()
					if False:
						if (sPwr >= 3) or (nSrate == 100e3):
							sampled_data = rh.runSamples(100)
						else:
							sampled_data = rh.runSamples(40)
					else:
						sampled_data = rh.runSamples(32)
					#print(sampled_data['EvmRms'])
				else: sampled_data=None
				#TODO: READ THE RX POWER!
				PRX=False
				#TODO: READ THE SIGNAL DATA
				if enabled:
					SIGNAL_WAVEFORM=rh.getDataChannel(2)				
				else: SIGNAL_WAVEFORM=None
				if enabled:
					SIGNAL_SAMPLE_POINTS=rh.getDataChannel(1)				
					SIGNAL_SAMPLE_SUB=(\
						SIGNAL_SAMPLE_POINTS[0][::20],\
						SIGNAL_SAMPLE_POINTS[1][::20],\
						)		
				else:
					SIGNAL_SAMPLE_POINTS=None
					SIGNAL_SAMPLE_SUB=None
				
				info_points = fh.tarinfo(name=(runName + '_points.json'))
				raw_pointsJson = json.dumps(SIGNAL_SAMPLE_POINTS).encode()
				info_points.size=len(raw_pointsJson)
				fh.addfile(tarinfo=info_points, fileobj=io.BytesIO(raw_pointsJson))
				
				info_points_data = fh.tarinfo(name=(runName + '_points_data.json'))
				raw_pointsDataJson = json.dumps(SIGNAL_SAMPLE_SUB).encode()
				info_points_data.size=len(raw_pointsDataJson)
				fh.addfile(tarinfo=info_points_data, fileobj=io.BytesIO(raw_pointsDataJson))
				
				info_waves = fh.tarinfo(name=(runName + '_waves.json'))
				raw_waveformsJson = json.dumps(SIGNAL_WAVEFORM).encode()
				info_waves.size=len(raw_waveformsJson)
				fh.addfile(tarinfo=info_waves, fileobj=io.BytesIO(raw_waveformsJson))
				
				RESULTS[iPwr]={\
					'PTX'	: float(sPwr), \
					'iPwr'	: iMod,\
					'PRX'	: PRX,\
					'DATA'	: sampled_data,\
					'MOD'	: sMod,\
					'iMOD'	: iMod,\
					'RATE'	: nSrate,\
					'iRATE'	: iSrate}
				rh.runFree()
			
			#for x in RESULTS[0]:
			#	print(type(RESULTS[0][x]), x)
			#print(json.dumps(RESULTS))
			# Aggregate power Data
			raw_string=json.dumps(RESULTS).encode()
			info_master_data.size=len(raw_string)
			fh.addfile(tarinfo=info_master_data, fileobj=io.BytesIO(raw_string))
			fh.close()
			print('================> SAVED %s' % localTarball)
			# LAST LINE OF MODULATION LOOP, start next modulation
			#break
		# LAST LINE OF SAMPLE RATE LOOP, start next rate
		#break
	#LAST LINE OF FUNCTION
	gh.setPower(-40)
############################################
			


# First open the two devices.
rh=	READc.sig_read(DRY=False)
gh=	GENc.sig_gen(rm=rh.rm, DRY=False)

rh.runFree()

freq_in = EngNumber(gh.ask("FREQ?"), 6)
print('Freq (gen): %s' % freq_in)
print('___ READY ___')

if False:
	rh.runSingle()


	f,ax=plt.subplots(1,1)
	x,y=rh.getDataChannel(1)

	if False:
		x,y=rh.getDataChannel(2)
		ax[1].plot(x,y)
		x,y=rh.getDataChannel(1)
		ax[0].plot(x,y)
		#x,y=rh.getDataChannel(3)
		#ax[0,1].plot(x,y)
		f.show()

	def plotVOffset(offset):
		print(offset)
		ax.clear()
		ax.plot(x[offset::step],y[offset::step])
		f.show()
		
	offset=0
	step=20
	#ax[0].plot(x,y)
	plotVOffset(0)


