#!/bin/env python
#-*- coding:utf-8 -*-


import json
import os
import sys
import time
import re
import commands
import platform


ENDPOINT = None
IP = None
STEP = 60


class RedisStats:
    # 如果你是自己编译部署到redis，请将下面的值替换为你到redis-cli路径
    _redis_cli = '/usr/bin/redis-cli'
    _stat_regex = re.compile(ur'(\w+):([0-9]+\.?[0-9]*)\r')

    def __init__(self,  port='6379', passwd=None, host='127.0.0.1'):
        self._cmd = '%s -h %s -p %s info' % (self._redis_cli, host, port)
        if passwd not in ['', None]:
            self._cmd = "%s -a %s" % (self._cmd, passwd)

    def stats(self):
        ' Return a dict containing redis stats '
        info = commands.getoutput(self._cmd)
        return dict(self._stat_regex.findall(info))


def main():
    if platform.system() != 'Linux':
        return

    global ENDPOINT
    global IP


    ENDPOINT = 'hostname'
    IP = "ip"
    step = 60
    timestamp = int(time.time())
    # If you using standard redis service uncommend lines below
    # inst_list中保存了redis配置文件列表，程序将从这些配置中读取port和password，建议使用动态发现的方法获得，如：
    # insts_list = [ i for i in commands.getoutput("sudo find  /etc/ -name 'redis*.conf'" ).split('\n') if 'sentinel' not in i]
    # insts_list = [ '/etc/redis.conf' ]
    p = []

    monit_keys = [
        ('connected_clients', 'GAUGE'),
        ('blocked_clients', 'GAUGE'),
        ('used_memory', 'GAUGE'),
        ('used_memory_rss', 'GAUGE'),
        ('mem_fragmentation_ratio', 'GAUGE'),
        ('total_commands_processed', 'COUNTER'),
        ('rejected_connections', 'COUNTER'),
        ('expired_keys', 'COUNTER'),
        ('evicted_keys', 'COUNTER'),
        ('keyspace_hits', 'COUNTER'),
        ('keyspace_misses', 'COUNTER'),
        ('keyspace_hit_ratio', 'GAUGE'),
    ]

    get_ports_cmd = "netstat -tanpl | grep codis | grep ' 0.0.0.0:*' | awk '{print $4}' | sed 's/0.0.0.0://g' "
    ports = commands.getoutput(get_ports_cmd).split()
    for port in ports:
        metric = "redis"
        endpoint = ENDPOINT
        tags = 'port=%s' % port
        tags = 'collect_type=agent,' + tags

        try:
            conn = RedisStats(port)
            stats = conn.stats()
        except Exception, e:
            continue

        for key, vtype in monit_keys:
            if key == 'keyspace_hit_ratio':
                try:
                    value = float(stats['keyspace_hits']) / (int(stats['keyspace_hits']) + int(stats['keyspace_misses']))
                except ZeroDivisionError:
                    value = 0
            elif key == 'mem_fragmentation_ratio':
                value = float(stats[key])
            else:
                try:
                    value = int(stats[key])
                except:
                    continue

            i = {
                'Metric': '%s.%s' % (metric, key),
                'Endpoint': endpoint,
                'Timestamp': timestamp,
                'Step': step,
                'Value': value,
                'CounterType': vtype,
                'TAGS': tags
            }
            p.append(i)

    print json.dumps(p, sort_keys=True, indent=4)

if __name__ == '__main__':
    if platform.system() != 'Linux':
        sys.exit(0)
    if not (os.path.isfile('/usr/bin/redis-cli') and os.access('/usr/bin/redis-cli', os.X_OK)):
        sys.exit(0)
    main()
