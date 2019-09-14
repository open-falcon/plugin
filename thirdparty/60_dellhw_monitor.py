#!/usr/bin/python
# coding:utf-8

import time
import json
import copy
import commands
import platform

payload = []

ENDPOINT = None
IP = None

data = {
    "endpoint": "",
    "metric": "",
    "timestamp": "",
    "step": 60,
    "value": "",
    "counterType": "",
    "tags": ""
}

dell_hw_cli = 'omreport'

metric_list = [
    {
        'metric': 'hardware.dell.battery',
        'cmd': ''' omreport chassis batteries|awk '/^Status/{if($NF=="Ok") {print 1} else {print 0}}' '''
    },
    {
        'metric': 'hardware.dell.cpu.model',
        'cmd': ''' awk -v hardware_cpu_crontol=`omreport  chassis biossetup|awk '/C State/{if($NF=="Enabled") {print 0} else {print  1}}'` -v hardware_cpu_c1=`omreport chassis biossetup|awk '/C1[-|E]/{if($NF=="Enabled") {print 0} else {print 1}}'` 'BEGIN{if(hardware_cpu_crontol==0 && hardware_cpu_c1==0) {print 0} else {print 1}}' '''
    },
    {
        'metric': 'hardware.dell.fan.health',
        'cmd': ''' awk -v hardware_fan_number=`omreport chassis fans|grep -c "^Index"` -v hardware_fan=`omreport chassis fans|awk '/^Status/{if($NF=="Ok") count+=1}END{print count}'` 'BEGIN{if(hardware_fan_number==hardware_fan) {print 1} else {print 0}}' '''
    },
    {
        'metric': 'hardware.dell.memory.health',
        'cmd': ''' awk -v hardware_memory=`omreport chassis memory|awk '/^Health/{print $NF}'` 'BEGIN{if(hardware_memory=="Ok") {print 1} else {print 0}}' '''
    },
    {
        'metric': 'hardware.dell.nic.health',
        'cmd': ''' awk -v hardware_nic_number=`omreport chassis nics |grep -c "Interface Name"` -v hardware_nic=`omreport chassis nics |awk '/^Connection Status/{print $NF}'|wc -l` 'BEGIN{if(hardware_nic_number==hardware_nic) {print 1} else {print 0}}' ''',
    },
    {
        'metric': 'hardware.dell.cpu',
        'cmd': ''' omreport chassis processors|awk '/^Health/{if($NF=="Ok") {print 1} else {print 0}}' ''',
    },
    {
        'metric': 'hardware.dell.power.health',
        'cmd': ''' awk -v hardware_power_number=`omreport chassis pwrsupplies|grep -c "Index"` -v hardware_power=`omreport chassis pwrsupplies|awk '/^Status/{if($NF=="Ok") count+=1}END{print count}'` 'BEGIN{if(hardware_power_number==hardware_power) {print 1} else {print 0}}' ''',
    },
    {
        'metric': 'hardware.dell.temp',
        'cmd': ''' omreport chassis temps|awk '/^Status/{if($NF=="Ok") {print 1} else {print 0}}'|head -n 1 ''',
    },
    {
        'metric': 'hardware.dell.physics.health',
        'cmd': ''' awk -v hardware_physics_disk_number=`omreport storage pdisk controller=0|grep -c "^ID"` -v hardware_physics_disk=`omreport storage pdisk controller=0|awk '/^Status/{if($NF=="Ok") count+=1}END{print count}'` 'BEGIN{if(hardware_physics_disk_number==hardware_physics_disk) {print 1} else {print 0}}' ''',
    },
    {
        'metric': 'hardware.dell.virtual.health',
        'cmd': ''' awk -v hardware_virtual_disk_number=`omreport storage vdisk controller=0|grep -c "^ID"` -v hardware_virtual_disk=`omreport storage vdisk controller=0|awk '/^Status/{if($NF=="Ok") count+=1}END{print count}'` 'BEGIN{if(hardware_virtual_disk_number==hardware_virtual_disk) {print 1} else {print 0}}' ''',
    },

]


def which(program):
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def push_payload(item):
    metric_data = copy.copy(data)
    ts = int(time.time())
    value = get_metric_value(item['cmd'])
    metric_data["endpoint"] = ENDPOINT
    metric_data["metric"] = item['metric']
    metric_data["value"] = int(value)
    metric_data["counterType"] = item['counterType'] if item.get('counterType') else 'GAUGE'
    metric_data["timestamp"] = ts
    metric_data["tags"] = "collect_type=plugin," + metric_data["tags"]
    payload.append(metric_data)


def get_metric_value(cmd):
    result = commands.getstatusoutput(cmd)
    if result[0]:
        return 0
    try:
        return_value = result[1]
    except ValueError:
        return_value = 0
    return return_value


def main():
    global ENDPOINT
    global IP

    if platform.system() != 'Linux':
        return

    fpath = which(dell_hw_cli)
    if fpath is None:
        return


    ENDPOINT = "hostname"
    IP = "IP"

    for item in metric_list:
        push_payload(item)
    print json.dumps(payload)


if __name__ == '__main__':
    main()
