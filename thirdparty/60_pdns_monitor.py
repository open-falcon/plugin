#!/bin/env python
# -*- coding:utf-8 -*-
import json
import time
import os
import sys
import commands
import platform

ENDPOINT = None
IP = None
step = 60
timestamp = int(time.time())
b = {}


def main():
    if platform.system() != 'Linux':
        return

    global ENDPOINT
    global IP
    p = []


    ENDPOINT = 'hostname'
    IP = 'ip'

    monit_keys = [
        ('questions', 'COUNTER'),
        ('packetcache-hits', 'COUNTER'),
        ('packetcache-misses', 'COUNTER'),
        ('cache-hits', 'COUNTER'),
        ('cache-misses', 'COUNTER'),
        ('answers0-1', 'COUNTER'),
        ('answers1-10', 'COUNTER'),
        ('answers10-100', 'COUNTER'),
        ('answers100-1000', 'COUNTER'),
        ('answers-slow', 'COUNTER'),
        ('qa-latency', 'GAUGE'),
        ('all-outqueries', 'COUNTER'),
        ('outgoing-timeouts', 'COUNTER'),
        ('throttled-out', 'COUNTER'),
        ('nxdomain-answers', 'COUNTER'),
        ('noerror-answers', 'COUNTER'),
        ('servfail-answers', 'COUNTER'),
        ('percentage cache hits', 'GAUGE'),
        ('percentage packet cache', 'GAUGE'),
        ('user-msec', 'COUNTER'),
        ('sys-msec', 'COUNTER')
    ]
    for key, vtype in monit_keys:
        get_value = "rec_control get" + " " + key
        # value = commands.getoutput(get_value).split()
        value = commands.getoutput(get_value)
        # print key+"---"+ value
        b[key] = value
        # print ''.join(b['questions'])
        if key == 'percentage cache hits':
            value = float(''.join(b['cache-hits'])) / (
                        float(''.join(b['cache-hits'])) + float(''.join(b['cache-misses']))) * 100
            value = str(value)[0:6]
        if key == 'percentage packet cache':
            value = float(''.join(b['packetcache-hits'])) / (
                        float(''.join(b['packetcache-hits'])) + float(''.join(b['packetcache-misses']))) * 100
            value = str(value)[0:6]

        # value = ("%.2f" % float(value))
        i = {
            'Metric': 'pdns.%s' % (key),
            'Endpoint': ENDPOINT,
            'Timestamp': timestamp,
            'Step': step,
            'Value': value,
            'CounterType': vtype,
            'TAGS': ''
        }
        p.append(i)
    print json.dumps(p, sort_keys=True, indent=4)


if __name__ == '__main__':
    if platform.system() != 'Linux':
        sys.exit(0)
    if not (os.path.isfile('/usr/bin/pdns_control')):
        sys.exit(0)
    main()
