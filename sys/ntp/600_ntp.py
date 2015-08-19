#!/usr/bin/env python
# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE
import json
import os
import time

data = []

def fetch_ntp_state():
    offset = 0
    try:
        raw_data = Popen(['ntpq', '-pn'], stdout=PIPE, stderr=PIPE).communicate()[0]
        for line in raw_data.splitlines():
            if line.startswith('*'):
                offset = line.split()[8]
    except OSError:
        pass

    create_record(offset)

def create_record(value):
    record = {}
    record['metric'] = 'sys.ntp.offset'
    record['endpoint'] = os.uname()[1]
    record['timestamp'] = int(time.time())
    record['step'] = 600
    record['value'] = abs(float(value))
    record['counterType'] = 'GAUGE'
    record['tags'] = ''
    data.append(record)

fetch_ntp_state()

if data:
    print json.dumps(data)
