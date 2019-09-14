#!/usr/bin/env python
# -*- coding:utf-8 -*-
# vim: set noet sw=4 ts=4 sts=4 ff=unix fenc=utf8:

import os
import sys
import json
import stat
import socket
import time
import platform

STEP = 60
STATS_FILE = "/var/lib/haproxy/stats"

class HaproxyStats(object):
    def __init__(self):
        self.StatsFile = "/var/lib/haproxy/stats"
        self.Debug = 5
        self.BufferSize = 8192
        self.EndpointName = "hostname"
        self.MetricPrefix = 'haproxy.'
        self.Metrics = ["qcur", "scur", "rate", "status",
                        "ereq", "econ", "dreq", "qtime", "ctime"]
        self._status = True
        self.socket_ = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    def __del__(self):
        self.socket_.close()

    def connect(self):
        try:
            if os.path.exists(self.StatsFile) and stat.S_ISSOCK(os.stat(self.StatsFile).st_mode):
                self.socket_.connect(self.StatsFile)
            else:
                print >> sys.stderr, "-- SOCK file: " + self.StatsFile + " dont exist"
                self._status = False
        except socket.error, msg:
            print >> sys.stderr, msg
            self._status = False

    def get_ha_stats(self):
        try:
            HS = []
            COMMAND = 'show stat\n'
            if self._status:
                self.socket_.send(COMMAND)
                data = self.socket_.recv(self.BufferSize)
                data = data.split("\n")
                for line in data:
                    Status = line.split(',')
                    if len(Status) < 2:
                        continue
                    if Status[32] == 'type':
                        Status[0] = Status[0].replace('#', '').strip()
                        Title = Status[0:-1]
                    else:
                        HS.append(Status)
                NewHS = []
                for MS in HS:
                    metric = {}
                    for header in Title:
                        i = Title.index(header)
                        metric[header] = 0 if len(str(MS[i])) == 0 else MS[i]
                    NewHS.append(metric)
            return NewHS
        except Exception, msg:
            print >> sys.stderr, msg
            return False

    def get_ha_info(self):
        try:
            COMMAND = 'show info\n'
            if self._status:
                self.socket_.send(COMMAND)
                data = self.socket_.recv(8192)
                return data
            else:
                self._status = False
        except socket.error, msg:
            print >> sys.stderr, msg

    def getMetric(self):
        UploadMetric = []
        upload_ts = int(time.time())
        self.connect()
        print 'fuck'
        if self._status:
            print 'shit'
            MyStats = self.get_ha_stats()
            if MyStats:
                print MyStats
                StatusCnt = 0
                for MS in MyStats:
                    Tag = 'pxname=' + MS['pxname'] + ',svname=' + MS['svname']
                    Tag = 'collect_type=plugin,' + Tag
                    for key, value in MS.iteritems():
                        if key not in self.Metrics:
                            continue
                        MetricName = self.MetricPrefix + key
                        if key == 'status':
                            if value == 'DOWN':
                                MetricValue = 1
                            else:
                                MetricValue = 0
                        else:
                            MetricValue = value
                        UploadMetric.append(
                            {"endpoint": self.EndpointName, "metric": MetricName, "tags": Tag, "timestamp": upload_ts,
                             "value": MetricValue, "step": 60, "counterType": "GAUGE"})
                        print MetricName
                getStatsFile = 0
            else:
                getStatsFile = 1
        else:
            getStatsFile = 2
        UploadMetric.append({"endpoint": self.EndpointName,
                             "metric": self.MetricPrefix + 'getstats',
                             "tags": 'collect_type=plugin,filename=' + self.StatsFile,
                             "timestamp": upload_ts, "value": getStatsFile,
                             "step": 60, "counterType": "GAUGE"})
        return UploadMetric

    def sendData(self):
        haproxy_metric = self.getMetric()
        print json.dumps(haproxy_metric)


if __name__ == "__main__":
    if platform.system() != 'Linux':
        sys.exit(0)

    if not os.path.exists(STATS_FILE):
        sys.exit(0)

    # upload monitor data to falcon server
    hs = HaproxyStats()
    hs.sendData()
