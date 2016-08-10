#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import sys
import platform
import math
import json

with open('config.json') as file:
	config = json.load(file)


def calcwork(scans=[]):
	totalwork = 0
	area = 0
	for rect in config['work']:
		distN = math.radians(max(rect[0], rect[2])-min(rect[0], rect[2]))*6371
		distE = math.radians(max(rect[3], rect[1])-min(rect[3], rect[1]))*6371*math.cos(math.radians((rect[0]+rect[2])*0.5))
		dlat = 0.00089
		dlng = dlat / math.cos(math.radians((rect[0]+rect[2])*0.5))
		startLat = min(rect[0], rect[2])+(0.624*dlat)
		startLng = min(rect[1], rect[3])+(0.624*dlng)
		latSteps = int((((max(rect[0], rect[2])-min(rect[0], rect[2])))/dlat)+0.75199999)
		if latSteps<1:
			latSteps=1
		lngSteps = int((((max(rect[1], rect[3])-min(rect[1], rect[3])))/dlng)+0.75199999)
		if lngSteps<1:
			lngSteps=1
		totalwork += latSteps * lngSteps
		for i in range(latSteps):
			for j in range(lngSteps):
				scans.append([startLat+(dlat*i), startLng+(dlng*j)])
		area += distN * distE
	return totalwork, area


def get_encryption_lib_path():
	lib_folder_path = os.path.join(
		os.path.dirname(__file__), "lib")
	lib_path = ""
	# win32 doesn't mean necessarily 32 bits
	if sys.platform == "win32":
		if platform.architecture()[0] == '64bit':
			lib_path = os.path.join(lib_folder_path, "encrypt64bit.dll")
		else:
			lib_path = os.path.join(lib_folder_path, "encrypt32bit.dll")

	elif sys.platform == "darwin":
		lib_path = os.path.join(lib_folder_path, "libencrypt-osx-64.so")

	elif os.uname()[4].startswith("arm") and platform.architecture()[0] == '32bit':
		lib_path = os.path.join(lib_folder_path, "libencrypt-linux-arm-32.so")

	elif sys.platform.startswith('linux'):
		if platform.architecture()[0] == '64bit':
			lib_path = os.path.join(lib_folder_path, "libencrypt-linux-x86-64.so")
		else:
			lib_path = os.path.join(lib_folder_path, "libencrypt-linux-x86-32.so")

	elif sys.platform.startswith('freebsd-10'):
		lib_path = os.path.join(lib_folder_path, "libencrypt-freebsd10-64.so")

	else:
		err = "Unexpected/unsupported platform '{}'".format(sys.platform)
		log.error(err)
		raise Exception(err)

	if not os.path.isfile(lib_path):
		err = "Could not find {} encryption library {}".format(sys.platform, lib_path)
		log.error(err)
		raise Exception(err)

	return lib_path

# vim: set ts=4 sw=4 tw=0 noet :
