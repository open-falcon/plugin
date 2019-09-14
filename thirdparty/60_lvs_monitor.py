#!/bin/env python
# -*- coding:utf-8 -*-


import json
import time
import os
import re
import commands
import urllib2

##start time 
Tstart = time.time() - 60
TIME_START_DAY = time.localtime(Tstart).tm_mday
TIME_START_HOUR = "%s:%s" % (str(time.localtime(Tstart).tm_hour).zfill(2), str(time.localtime(Tstart).tm_min).zfill(2))
TIME_START_MON = time.strftime("%b", time.localtime(time.time()))
TIME_START = "%s  %s %s" % (TIME_START_MON, TIME_START_DAY, TIME_START_HOUR)

##end time 
Tend = time.time()
TIME_END_DAY = time.localtime(Tend).tm_mday
TIME_END_HOUR = "%s:%s:%s" % (str(time.localtime(Tend).tm_hour).zfill(2), str(time.localtime(Tend).tm_min).zfill(2),
                              str(time.localtime(Tend).tm_sec).zfill(2))
TIME_END_MON = time.strftime("%b", time.localtime(time.time()))
TIME_END = "%s  %s %s" % (TIME_END_MON, TIME_END_DAY, TIME_END_HOUR)
# 接受日志监控URL 可以不传
content_post_url = "http://127.0.0.1:8080/api/v1/context/"
LOG_DIR = '/var/log/messages'
step = 60
IP = "IP"
ENDPOINT = "hostname"

RESULT_PATTERN_REALSERVER = re.compile(
    r'.*\W(\d+:\d+:\d+).*healthcheckers:\W+(.*ling) service (\[\d+.*\]:\d+)\s.* VS\s+\[(.*)\]:\d+')
RESULT_PATTERN_VIP = re.compile(r'.*\W(\d+:\d+:\d+).*zl.py (.*) (\d\d.*);] for VS \[(.*)\]')


def main():
    if not os.path.exists("/proc/net/ip_vs_stats"):
        exit()
    realserver_value = 0
    realserver_msg = []
    vip_value = 0
    vip_msg = []
    cmd = 'awk \'/%s/,/%s/\' %s | grep Keepalived_healthcheckers' % (TIME_START, TIME_END, LOG_DIR)
    (status, output) = commands.getstatusoutput(cmd)
    for line in output.splitlines():
        if "ling service" in line:
            match = RESULT_PATTERN_REALSERVER.search(line)
            dt = match and match.group(1)
            status = match and match.group(2).replace("Disabling", "failed").replace("Enabling", "succes")
            realserver = (match and match.group(3)).replace("[", "").replace("]", "")
            url = match and match.group(4)
            realserver_msg.append("%s %s-%s connection-----%s" % (dt, url, realserver, status))
            if status == "failed":
                realserver_value += 1
        elif "Executing" in line:
            match = RESULT_PATTERN_VIP.search(line)
            url = match and match.group(4)
            vip = match and match.group(3)
            dt = match and match.group(1)
            status = match and match.group(2).replace("-d", "failed").replace("-c", "succes")
            vip_msg.append("%s %s-%s-----%s" % (dt, url, vip, status))
            if status == "failed":
                vip_value += 1
    push_data = [
        {
            'metric': 'lvs.log.monitor',
            'endpoint': ENDPOINT,
            'timestamp': int(time.time()),
            'step': step,
            'value': realserver_value,
            'counterType': 'GAUGE',
            'tags': "type=realserver"
        },
        {
            'metric': 'lvs.log.monitor',
            'endpoint': ENDPOINT,
            'timestamp': int(time.time()),
            'step': step,
            'value': vip_value,
            'counterType': 'GAUGE',
            'tags': "type=vip"
        },
    ]
    print json.dumps(push_data)

    # 以下为推送日志信息
    # realserver_msg_content = "\n".join(realserver_msg) or "all ok"
    # vip_msg_content = "\n".join(vip_msg) or "all ok"
    # push_data[0]["context"] = realserver_msg_content
    # push_data[1]["context"] = vip_msg_content
    # try:
    #     req = urllib2.Request(content_post_url)
    #     resp = urllib2.urlopen(req, json.dumps(push_data))
    # except Exception, e:
    #     pass


if __name__ == '__main__':
    main()
