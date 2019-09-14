#!/usr/bin/python
# -*- coding:utf-8 -*-
import re
import os
import time
import requests
import json
from collections import defaultdict
from netaddr import IPAddress


def NetTraffic():
    '''
    Inter-|   Receive                                                |  Transmit
     face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
        lo:1575908630 17026737    0    0    0     0          0         0 1575908630 17026737    0    0    0     0       0          0
       em1:11349180581701 15272341772    0  281    0 30780          0 6989404564 1048307243792 4560099108    0    0    0     0       0          0
       em2:469087486302 2564818739    0    0    0     0          0 526281272 97236008717 565164959    0    0    0     0       0          0
    '''

    net_reg = re.compile(":")
    flow1 = open('/proc/net/dev')
    lines = flow1.readlines()
    flow1.close()
    netIfs = defaultdict(dict)

    for i in lines:
        if net_reg.search(i) and not (re.search('lo', i) or re.search('bond', i)):
            inter = i.strip().split(":")[0]
            res = ' '.join(re.split(' +|\n+', i.strip().split(':')[1])).strip().split(' ')

            netIfs[inter]['InBytes'] = res[0]
            netIfs[inter]['InPackages'] = res[1]
            netIfs[inter]['InErrors'] = res[2]
            netIfs[inter]['InDropped'] = res[3]
            netIfs[inter]['InFifoErrs'] = res[4]
            netIfs[inter]['InFrameErrs'] = res[5]
            netIfs[inter]['InCompressed'] = res[6]
            netIfs[inter]['InMulticast'] = res[7]

            netIfs[inter]['OutBytes'] = res[8]
            netIfs[inter]['OutPackages'] = res[9]
            netIfs[inter]['OutErrors'] = res[10]
            netIfs[inter]['OutDropped'] = res[11]
            netIfs[inter]['OutFifoErrs'] = res[12]
            netIfs[inter]['OutFrameErrs'] = res[13]
            netIfs[inter]['OutCompressed'] = res[14]
            netIfs[inter]['OutMulticast'] = res[15]

    return netIfs


def SYSNetWorks(ifcfg='/etc/sysconfig/network-scripts/ifcfg-%s', ifaces=None):
    '''
    DEVICE=eth3
    TYPE=Ethernet
    ONBOOT=yes
    NM_CONTROLLED=no
    BOOTPROTO=no
    ARPCHECK=no
    USERCTL=no
    IPV6INIT=no
    MASTER=bond0
    SLAVE=yes

    返回wan/lan网口名称 bonding后的口不计算为wan口流量

    :return:
    '''

    sys_config = defaultdict(dict)
    for iface in ifaces:
        with open(ifcfg % iface) as f:
            for content in f.readlines():
                try:
                    ifKey, ifVal = content.strip().split("=")
                    ifKey = ifKey.lower()
                    sys_config[iface][ifKey] = ifVal
                except Exception as e:
                    continue

    return sys_config


def NetIfs(netIfs=None, ifaces=None):
    '''
    公网和内网流量汇聚
    :return:
    '''

    bonding = False
    wan_nic = list()
    lan_nic = list()
    for iface in ifaces:

        device = netIfs.get(iface).get('device')
        master = netIfs.get(iface).get('master')
        ipaddr = netIfs.get(iface).get('ipaddr')

        if ipaddr:
            private = IPAddress(ipaddr).is_private()
            if private:
                lan_nic.append(device)
            else:
                wan_nic.append(device)
        if master:
            wan_nic.append(device)

    return (list(set(wan_nic)), lan_nic)


def get_hostname():
    res_command = os.popen('hostname').read().strip()
    return res_command if res_command else 'unknown'


def get_send_json(metric=None):
    playload_lst = list()
    for tag in metric.keys():
        for k, v in metric[tag].items():
            playload = {
                "endpoint": get_hostname(),
                "metric": k,
                "timestamp": int(time.time()),
                "step": 60,
                "value": v,
                "counterType": "COUNTER",
                "tags": "iface=%s" % tag
            }

            playload_lst.append(playload)

    return playload_lst


def Ifstat():
    netIfs = NetTraffic()
    sysNetWorks = SYSNetWorks(ifaces=netIfs.keys())
    wan_face, lan_face = NetIfs(sysNetWorks, ifaces=netIfs.keys())
    metric = defaultdict(dict)

    metric['wan']['net.if.in.bytes'] = 0
    metric['wan']['net.if.in.errors'] = 0
    metric['wan']['net.if.out.bytes'] = 0
    metric['wan']['net.if.out.errors'] = 0

    metric['lan']['net.if.in.bytes'] = 0
    metric['lan']['net.if.in.errors'] = 0
    metric['lan']['net.if.out.bytes'] = 0
    metric['lan']['net.if.out.errors'] = 0

    for face in wan_face:
        metric['wan']['net.if.in.bytes'] += int(netIfs.get(face).get('InBytes')) * 8
        metric['wan']['net.if.in.errors'] += int(netIfs.get(face).get('InErrors')) * 8
        metric['wan']['net.if.out.bytes'] += int(netIfs.get(face).get('OutBytes')) * 8
        metric['wan']['net.if.out.errors'] += int(netIfs.get(face).get('OutErrors')) * 8

    for face in lan_face:
        metric['lan']['net.if.in.bytes'] += int(netIfs.get(face).get('InBytes')) * 8
        metric['lan']['net.if.in.errors'] += int(netIfs.get(face).get('InErrors')) * 8
        metric['lan']['net.if.out.bytes'] += int(netIfs.get(face).get('OutBytes')) * 8
        metric['lan']['net.if.out.errors'] += int(netIfs.get(face).get('OutErrors')) * 8

    playload = get_send_json(metric)
    r = requests.post("http://127.0.0.1:1988/v1/push", data=json.dumps(playload))


if __name__ == '__main__':
    Ifstat()
