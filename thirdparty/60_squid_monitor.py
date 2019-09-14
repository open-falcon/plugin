#!/usr/bin/python
# coding:utf-8

import time
import json
import copy
import commands
import threading
import subprocess
import traceback
import shlex
import tempfile
import os
import platform
import sys

## const data you can edit this
payload = []

data = {
    "endpoint": "",
    "metric": "",
    "timestamp": "",
    "step": 60,
    "value": "",
    "counterType": "",
    # "tags": "collect_type=plugin" + tags
    "tags": ""
}

ENDPOINT = None
IP = None
STEP = 60

MetricLists = [
    {
        'metric': 'squid.http.requests',
        'cmd': ''' cat %s |grep 'Number of HTTP requests received:'|cut -d':' -f2| tr -d ' \t' '''
    },
    {
        'metric': 'squid.cache.miss',
        'cmd': ''' cat %s  |grep "Cache Misses" |awk '{print $3}' '''
    },
    {
        'metric': 'squid.clients',
        'cmd': ''' cat %s |grep 'Number of clients accessing cache:'|cut -d':' -f2| tr -d ' \t' '''
    },
    {
        'metric': 'squid.client.http.request',
        'cmd': ''' cat  %s |grep 'client_http.requests'|awk '{print $3}' |cut -d'/' -f1 '''
    },
    {
        'metric': 'squid.client.http.hits',
        'cmd': ''' cat  %s |grep 'client_http.hits'|awk '{print $3}'|cut -d'/' -f1 '''
    },
    {
        'metric': 'squid.req.fail.ratio',
        'cmd': ''' cat  %s |grep 'Request failure ratio:'|cut -d':' -f2| tr -d ' \t' '''
    },
    {
        'metric': 'squid.avg.http.msg.min',
        'cmd': ''' cat  %s |grep 'Average HTTP requests per minute since start:'|cut -d':' -f2| tr -d ' \t' '''
    },
    {
        'metric': 'squid.avg.icp.msg.min',
        'cmd': ''' cat  %s |grep 'Average ICP messages per minute since start:'|cut -d':' -f2| tr -d ' \t' '''
    },
    # escape %
    {
        'metric': 'squid.request.hit.ratio',
        'cmd': ''' cat  %s |grep 'Request Hit Ratios:'|cut -d':' -f3|cut -d',' -f1|tr -d ' %%' '''
    },
    {
        'metric': 'squid.byte.hit.ratio',
        'cmd': ''' cat  %s |grep 'Byte Hit Ratios:'|cut -d':' -f3|cut -d',' -f1|tr -d ' %%' '''
    },
    {
        'metric': 'squid.request.mem.hit.ratio',
        'cmd': '''  cat  %s |grep 'Request Memory Hit Ratios:'|cut -d':' -f3|cut -d',' -f1|tr -d ' %%' '''
    },
    {
        'metric': 'squid.request.disk.hit.ratio',
        'cmd': ''' cat  %s |grep 'Request Disk Hit Ratios:'|cut -d':' -f3|cut -d',' -f1|tr -d ' %%' '''
    },
    {
        'metric': 'squid.servicetime.httpreq',
        'cmd': ''' cat  %s |grep 'HTTP Requests (All):'|cut -d':' -f2|tr -s ' '|awk '{print $1}' '''
    },
    {
        'metric': 'squid.process.mem',
        'cmd': ''' cat  %s |grep 'Process Data Segment Size via sbrk'|cut -d':' -f2|awk '{print $1}' '''
    },
    {
        'metric': 'squid.cpu.usage',
        'cmd': ''' cat  %s |grep 'CPU Usage:'|cut -d':' -f2|tr -d '%%'|tr -d ' \t' '''
    },
    {
        'metric': 'squid.cache.size.disk',
        'cmd': ''' cat  %s |grep 'Storage Swap size:'|cut -d':' -f2|awk '{print $1}' '''
    },
    {
        'metric': 'squid.cache.size.mem',
        'cmd': ''' cat  %s |grep 'Storage Mem size:'|cut -d':' -f2|awk '{print $1}' '''
    },
    {
        'metric': 'squid.mean.obj.size',
        'cmd': ''' cat  %s |grep 'Mean Object Size:'|cut -d':' -f2|awk '{print $1}' '''
    },
    {
        'metric': 'squid.filedescr.max',
        'cmd': ''' cat  %s |grep 'Maximum number of file descriptors:'|cut -d':' -f2|awk '{print $1}' '''
    },
    {
        'metric': 'squid.filedescr.avail',
        'cmd': ''' cat  %s |grep 'Available number of file descriptors:'|cut -d':' -f2|awk '{print $1}' '''
    }

]

squid_info_cmd = 'squidclient -p %s -h %s mgr:info'
squid_5min_cmd = 'squidclient -p %s -h %s mgr:5min'

squid_client_path = '/usr/local/bin/squidclient'


## end const

class Command(object):
    """
    Enables to run subprocess commands in a different thread with TIMEOUT option.
    Based on jcollado's solution:
    http://stackoverflow.com/questions/1191374/subprocess-with-timeout/4825933#4825933
    """
    command = None
    process = None
    status = None
    output, error = '', ''

    def __init__(self, command):
        if isinstance(command, basestring):
            command = shlex.split(command)
        self.command = command

    def run(self, timeout=None, **kwargs):
        """ Run a command then return: (status, output, error). """

        def target(**kwargs):
            try:
                self.process = subprocess.Popen(self.command, **kwargs)
                self.output, self.error = self.process.communicate()
                self.status = self.process.returncode
            except:
                self.error = traceback.format_exc()
                self.status = -1

        # default stdout and stderr
        if 'stdout' not in kwargs:
            kwargs['stdout'] = subprocess.PIPE
        if 'stderr' not in kwargs:
            kwargs['stderr'] = subprocess.PIPE
        # thread
        thread = threading.Thread(target=target, kwargs=kwargs)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            self.process.terminate()
            thread.join()
        return self.status, self.output, self.error


def push_payload(item, tmp_filename, name, payload):
    metric_data = copy.copy(data)
    ts = int(time.time())
    if "proc.num" in item['metric']:
        cmd = item['cmd'] % "squid"
    else:
        cmd = item['cmd'] % tmp_filename
    value = get_metric_value(cmd)
    metric_data["endpoint"] = ENDPOINT
    metric_data["metric"] = item['metric']
    metric_data["value"] = value
    metric_data["counterType"] = item['counterType'] if item.get('counterType') else 'GAUGE'
    metric_data["timestamp"] = ts
    metric_data["tags"] = tags
    payload.append(metric_data)


def get_metric_value(cmd):
    result = commands.getstatusoutput(cmd)
    if not result[1]:
        return 0
    try:
        return_value = float(result[1])
    except ValueError:
        return_value = 0
    return return_value


def get_payload(metrics_list, step):
    ts = int(time.time())
    payloads = []
    for metric_item in metrics_list:

        metric_dict = get_metric_dict(metric_item, ts, step)
        if not metric_dict:
            continue
        payloads.append(metric_dict)
    return payloads


def main():
    if platform.system() != 'Linux':
        return

    global ENDPOINT
    global IP
    global tags
    # auto discovery
    if not os.path.isfile(squid_client_path):
        return

    ENDPOINT = 'hostname'
    IP = 'ip'

    payload = []
    squid_name = ['squid1', 'squid2', 'squid3']
    for host in range(1):
        squidps = int(commands.getoutput("ps -ef|grep -E  'squid.conf'|grep -v grep |wc -l")) / 2
        for name in squid_name:
            squid_ip = []
            if os.path.isfile('/usr/local/%s/etc/squid.conf' % (name)) == True:
                tags = "collect_type=plugin" + ',' + 'type=' + name
                squid_ip.append(commands.getoutput(
                    "grep -E '[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}' /usr/local/%s/etc/squid.conf | grep http_port|grep -v ^#|awk '{print $2}'|awk -F: '{print $1}'" % (
                        name)))
                ts = int(time.time())
                get_proc = "ps -ef |grep %s|grep -v grep |wc -l" % name
                proc = commands.getoutput(get_proc)
                i = {
                    'Metric': "squid.proc.num",
                    'Endpoint': ENDPOINT,
                    'Timestamp': ts,
                    'Step': '60',
                    'Value': proc,
                    'CounterType': 'GAUGE',
                    'TAGS': tags
                }
                payload.append(i)
            for ip in squid_ip:
                name = ENDPOINT
                with tempfile.NamedTemporaryFile() as temp:
                    cmd1_str = squid_info_cmd % ("80", ip)
                    cmd2_str = squid_5min_cmd % ("80", ip)
                    cmd1 = Command(cmd1_str)
                    cmd2 = Command(cmd2_str)
                    cmd1.run()
                    cmd2.run()
                    if cmd1.status == -1 and cmd2.status == -1:
                        break
                    temp.write(cmd1.output)
                    temp.flush()
                    temp.write(cmd2.output)
                    temp.flush()
                    for item in MetricLists:
                        push_payload(item, temp.name, name, payload)
    print json.dumps(payload)


if __name__ == '__main__':
    if platform.system() != 'Linux':
        sys.exit(0)
    if not (os.path.isfile('/usr/local/bin/squidclient')):
        sys.exit(0)
    main()
