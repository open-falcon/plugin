#! /usr/bin/env python
#-*- coding:utf-8 -*-

import json
import time

data = [
        {
            'metric': 'plugins.xx',
            'endpoint': 'host-001.bj',
            'timestamp': int(time.time()),
            'step': 60,
            'value': 1,
            'counterType': 'GAUGE',
            'tags': 'idc=aa'
            },
        {
            'metric': 'plugins.yy',
            'endpoint': 'host-002.bj',
            'timestamp': int(time.time()),
            'step': 60,
            'value': 0,
            'counterType': 'GAUGE',
            'tags': 'idc=bb'
            }
        ]

print(json.dumps(data))
