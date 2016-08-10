#!/usr/bin/env python2
import json
import math
import os
import logging
import time
import geojson

import threading
import utils

from pgoapi import pgoapi
from pgoapi import utilities as util
from pgoapi.exceptions import NotLoggedInException, ServerSideRequestThrottlingException, ServerBusyOrOfflineException

from s2sphere import CellId, LatLng

pokes = {}
spawns = {}
stops = {}
gyms = {}

scans = []
num2words = ['first','second','third','forth','fith','sixth']

#config file
with open('config.json') as file:
	config = json.load(file)

def doScanp(wid, sLat, sLng, api):
	for i in range(0,10):
		try:
			doScan(wid, sLat, sLng, api)
		except (KeyError,TypeError):
			print('thread {} error scan returned error, retry {}/10').format(wid,i)
			time.sleep(config['scanDelay'])
			continue
		else:
			break

def doScan(wid, sLat, sLng, api):
	#print ('scanning ({}, {})'.format(sLat, sLng))
	api.set_position(sLat,sLng,0)
	cell_ids = util.get_cell_ids(lat=sLat, long=sLng, radius=80)
	timestamps = [0,] * len(cell_ids)
	while True:
		try:
			response_dict = api.get_map_objects(latitude = sLat, longitude = sLng, since_timestamp_ms = timestamps, cell_id = cell_ids)
		except  ServerSideRequestThrottlingException:
			config['scanDelay'] += 0.5
			print ('Worker-{} Request throttled, increasing sleep by 0.5 to {}').format(wid,config['scanDelay'])
			time.sleep(config['scanDelay'])
			continue
		except:
			time.sleep(config['scanDelay'])
			api.set_position(sLat,sLng,0)
			time.sleep(config['scanDelay'])
			continue
		break

	try:
		cells = response_dict['responses']['GET_MAP_OBJECTS']['map_cells']
	except TypeError:
		print ('thread {} error getting map data for {}, {}'.format(wid,sLat, sLng))
		raise
	except KeyError:
		print ('thread {} error getting map data for {}, {}'.format(wid,sLat, sLng))
		raise
		return
	for cell in cells:
		curTime = cell['current_timestamp_ms']
		if 'wild_pokemons' in cell:
			for wild in cell['wild_pokemons']:
				if wild['time_till_hidden_ms']>0:
					timeSpawn = (curTime+(wild['time_till_hidden_ms']))-900000
					gmSpawn = time.gmtime(int(timeSpawn/1000))
					secSpawn = (gmSpawn.tm_min*60)+(gmSpawn.tm_sec)
					phash = '{},{}'.format(timeSpawn,wild['spawn_point_id'])
					shash = '{},{}'.format(secSpawn,wild['spawn_point_id'])
					pokeLog = {'time':timeSpawn, 'sid':wild['spawn_point_id'], 'lat':wild['latitude'], 'lng':wild['longitude'], 'pid':wild['pokemon_data']['pokemon_id'], 'cell':CellId.from_lat_lng(LatLng.from_degrees(wild['latitude'], wild['longitude'])).to_token()}
					spawnLog = {'time':secSpawn, 'sid':wild['spawn_point_id'], 'lat':wild['latitude'], 'lng':wild['longitude'], 'cell':CellId.from_lat_lng(LatLng.from_degrees(wild['latitude'], wild['longitude'])).to_token()}
					pokes[phash] = pokeLog
					spawns[shash] = spawnLog
		if 'forts' in cell:
			for fort  in cell['forts']:
				if fort['enabled'] == True:
					if 'type' in fort:
						#got a pokestop
						stopLog = {'id':fort['id'],'lat':fort['latitude'],'lng':fort['longitude'],'lure':-1}
						if 'lure_info' in fort:
							stopLog['lure'] = fort['lure_info']['lure_expires_timestamp_ms']
						stops[fort['id']] = stopLog
					if 'gym_points' in fort:
						gymLog = {'id':fort['id'],'lat':fort['latitude'],'lng':fort['longitude'],'team':0}
						if 'owned_by_team' in fort:
							gymLog['team'] = fort['owned_by_team']
						gyms[fort['id']] = gymLog
	time.sleep(config['scanDelay'])

def worker(wid,Wstart,numWorkers):
	workStart = min(Wstart,len(scans)-1)
	workStop = min(Wstart+config['stepsPerPassPerWorker'],len(scans)-1)
	if workStart == workStop:
		return
	print ('worker {} is doing steps {} to {}').format(wid,workStart,workStop)
	#Offset worker startup to minimize auto throttle.
	time.sleep(1*wid)
	#login
	api = pgoapi.PGoApi(provider=config['auth_service'], username=config['users'][wid]['username'], password=config['users'][wid]['password'], position_lat=0, position_lng=0, position_alt=0)
	api.activate_signature(utils.get_encryption_lib_path())
	api.get_player()
	#iterate
	for j in range(5):
		startTime = time.time()
		print ('worker {} is doing {} pass').format(wid,num2words[j])
		for i in xrange(workStart,workStop):
			doScanp(wid,scans[i][0], scans[i][1], api)
		curTime=time.time()
		if 600-(curTime-startTime) > 0:
			print ('worker {} took {} seconds to do {} pass now sleeping for {}').format(wid,curTime-startTime,j,600-(curTime-startTime))
			time.sleep(600-(curTime-startTime))
		else:
			print ('worker {} took {} seconds to do pass so not sleeping').format(wid,curTime-startTime,j)
	startTime = time.time()
	print ('worker {} is doing {} pass').format(wid,num2words[5])
	for i in xrange(workStart,workStop):
		doScanp(wid,scans[i][0], scans[i][1], api)
	curTime=time.time()
	print ('worker {} took {} seconds to do {} pass ending thread').format(wid,curTime-startTime,num2words[5])

def main():
	tscans,tarea = utils.calcwork(scans)
	print ('total of {} steps covering {} km^2').format(tscans,tarea)
	numWorkers = ((tscans-1)//config['stepsPerPassPerWorker'])+1
	if numWorkers > len(config['users']):
		numWorkers = len(config['users'])
	print ('with {} workers, doing {} scans each, would take {} hours').format(numWorkers,config['stepsPerPassPerWorker'],int(math.ceil(float(tscans)/(numWorkers*config['stepsPerPassPerWorker']))))
	if (config['stepsPerPassPerWorker']*config['scanDelay']) > 600:
		print ('error. scan will take more than 10mins so all 6 scans will take more than 1 hour')
		print ('please try using less scans per worker')
		return
	#heres the logging setup
	# log settings
	# log format
	logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(module)10s] [%(levelname)5s] %(message)s')
	# log level for http request class
	logging.getLogger("requests").setLevel(logging.WARNING)
	# log level for main pgoapi class
	logging.getLogger("pgoapi").setLevel(logging.WARNING)
	# log level for internal pgoapi class
	logging.getLogger("rpc_api").setLevel(logging.WARNING)

	if config['auth_service'] not in ['ptc', 'google']:
		log.error("Invalid Auth service specified! ('ptc' or 'google')")
		return None
#setup done

	threads = []
	scansStarted = 0
	for i in xrange(len(config['users'])):
		if scansStarted >= len(scans):
			break;
		t = threading.Thread(target=worker, args = (i,scansStarted,numWorkers))
		t.start()
		threads.append(t)
		scansStarted += config['stepsPerPassPerWorker']
	while scansStarted < len(scans):
		time.sleep(15)
		for i in xrange(len(threads)):
			if not threads[i].isAlive():
				threads[i] = threading.Thread(target=worker, args = (i,scansStarted))
				threads[i].start()
				scansStarted += config['stepsPerPassPerWorker']
	for t in threads:
		t.join()
	print ('all done. saving data')

	out = []
	for poke in pokes.values():
		out.append(poke)
	f = open('pokes.json','w')
	json.dump(out,f)
	f.close()

	out = []
	for poke in spawns.values():
		out.append(poke)
	f = open('spawns.json','w')
	json.dump(out,f)
	f.close()

	out = []
	for poke in stops.values():
		out.append(poke)
	f = open('stops.json','w')
	json.dump(out,f)
	f.close()

	out = []
	for poke in gyms.values():
		out.append(poke)
	f = open('gyms.json','w')
	json.dump(out,f)
	f.close()

#output GeoJSON data
	with open('gyms.json') as file:
		items = json.load(file)
	geopoints = []
	for location in items:
		point = geojson.Point((location['lng'], location['lat']))
		feature = geojson.Feature(geometry=point, id=location['id'],properties={"name":location['id']})
		geopoints.append(feature)
	features = geojson.FeatureCollection(geopoints)
	f = open('geo_gyms.json','w')
	json.dump(features,f)
	f.close()

	with open('stops.json') as file:
		items = json.load(file)
	geopoints = []
	for location in items:
		point = geojson.Point((location['lng'], location['lat']))
		feature = geojson.Feature(geometry=point, id=location['id'],properties={"name":location['id']})
		geopoints.append(feature)
	features = geojson.FeatureCollection(geopoints)
	f = open('geo_stops.json','w')
	json.dump(features,f)
	f.close()

if __name__ == '__main__':
	main()

# vim: set ts=4 sw=4 tw=0 noet :
