#!/usr/bin/env python2
import json
import math
import utils

with open('config.json') as file:
	config = json.load(file)

tscans,tarea = utils.calcwork()
print 'total of {} steps covering {} km^2'.format(tscans,tarea)
numWorkers = ((tscans-1)//config['stepsPerPassPerWorker'])+1
if numWorkers > len(config['users']):
	numWorkers = len(config['users'])
print 'with {} workers, doing {} scans each, would take {} hours'.format(numWorkers,config['stepsPerPassPerWorker'],int(math.ceil(float(tscans)/(config['stepsPerPassPerWorker']*numWorkers))))

# vim: set ts=4 sw=4 tw=0 noet :
