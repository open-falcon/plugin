#! /usr/bin/env python
# -*- coding: utf-8 -*-

import time, os, socket
import json

metric = ['usr', 'nice', 'sys', 'idle', 'iowait', 'irq', 'soft', 'steal', 'guest']
host = socket.gethostname()

def get_cpu_core_stat(num):
  data = []
  for x in range(num):
    try:
      handler = os.popen("cat /proc/stat | grep cpu%d " % x)
    except:
      continue

    output = handler.read().strip().split()[1:]

    if len(output) != 9:
      continue

    index=0
    for m in output:
      t = {}
      t['metric'] = 'cpu.core.%s' % metric[index]
      t['endpoint'] = host
      t['timestamp'] = int(time.time())
      t['step'] = 60
      t['counterType'] = 'COUNTER'
      t['tags'] = 'core=%s' % str(x)
      t['value'] = m
      index += 1
      data.append(t)

  return data

if __name__ == "__main__":
  core_total = int(os.popen("cat /proc/cpuinfo | grep processor | tail -1 | cut -d' ' -f2").read().strip()) + 1
  print json.dumps(get_cpu_core_stat(core_total))
