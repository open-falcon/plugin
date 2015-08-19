#!/usr/bin/env python
# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE
from tempfile import TemporaryFile
import json
import os
import time

data = []

def get_all_mountpoint():
    raw_data = Popen(['df', '-P'], stdout=PIPE, stderr=PIPE).communicate()[0].splitlines()
    mountpoints = []
    for line in raw_data:
        if line:
            element = line.split()[5]
            if element.startswith('/'):
                mountpoints.append(element)
    return mountpoints


for path in get_all_mountpoint():
    rstr = '@8qJnD&Y'
    value = 0
    try:
        fd = TemporaryFile(dir=path)
        fd.write(rstr)
        fd.flush()
        fd.seek(0)
        content = fd.readline()
        fd.close()

        if rstr != content:
            value = 1
    except OSError, IOError:
        value = 1

    record = {}
    record['metric'] = 'sys.disk.rw'
    record['endpoint'] = os.uname()[1]
    record['timestamp'] = int(time.time())
    record['step'] = 60
    record['value'] = value
    record['counterType'] = 'GAUGE'
    record['tags'] = 'mount=%s' % path
    data.append(record)

if data:
    print json.dumps(data)
