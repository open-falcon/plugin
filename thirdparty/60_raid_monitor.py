#!/usr/bin/python
# coding:utf-8
import socket
import time
import json
import copy
import subprocess as sp
import re
import sys
import os
import platform

Command = {"AdpCount": "%s -AdpCount -NoLog", "PD_NUM": "%s -pdGetNum -a %d -NoLog",
           "LDS_NUM": "%s -LDGetNum -a %d -NoLog", "VD_LIST": "%s -LDinfo -Lall -a %d -NoLog", \
           "BBU_INFO": "%s -AdpBbuCmd -GetBbuStatus -a %d -NoLog", "PD_LIST": "%s  -pdlist -a %d -NoLog",
           "CLI_OUT": "%s -pdinfo -PhysDrv[%s:%s] -a %s -NoLog", \
           "BBU_OUT": "%s -AdpBbuCmd %s -a %s -NoLog", "ADP_OUT": "%s -AdpAllInfo -a %s -NoLog"}

cli = "/opt/MegaRAID/MegaCli/MegaCli64"

payload = []

ENDPOINT = None
IP = None
STEP = 60


def get_metric_value(args1):
    p = sp.Popen(args1, shell=True, stdout=sp.PIPE, stderr=sp.STDOUT)
    # // 这儿不能用wait返回值这个用法了 (返回值一直是1,可能跟Exit Code: 0x01有关系)
    retval = p.wait()
    result = p.stdout.readlines()
    return result


def get_func_value(_comm, _rep, num=1):
    for _i in get_metric_value(_comm):
        _b = _rep.match(_i)
        if _b:
            return _b.group(num)
    return None


def get_metric_dict(item, value, tags='', tp="GAUGE", step=STEP):
    ts = int(time.time())
    data = {}
    data["endpoint"] = ENDPOINT
    data["metric"] = item
    data["step"] = step
    data["value"] = value
    data["counterType"] = tp
    data["timestamp"] = ts
    data["tags"] = "collect_type=plugin," + tags
    payload.append(data)
    return data


def main():
    if platform.system == 'Linux':
        return

    global ENDPOINT
    global IP


    ENDPOINT = 'hostname'
    IP = 'ip'

    if not os.path.isfile(cli):
        return

    a = re.compile(".*Controller\sCount:\s(\d)\.*")
    _AdpCount = Command["AdpCount"] % (cli)
    adp_count = get_func_value(_AdpCount, a);
    if adp_count == None:
        print "Didn't find any adapter, check regex or %s\n" % cli;
        sys.exit(0)
    else:
        # 获得raid卡的数量
        adp_count = int(adp_count)

    for adapter in range(adp_count):
        b = re.compile(".*Number\sof\sPhysical\sDrives\son\sAdapter\s%d:\s(\d+).*" % adapter)
        _PD_NUM = Command["PD_NUM"] % (cli, adapter)
        pd_num = get_func_value(_PD_NUM, b);
        if pd_num != None:
            pd_num = int(pd_num)
        if pd_num == 0:
            print "No physical disks found on adapter %d\n" % adapter;
            continue
        else:
            # -----------------adapter------------------------
            re_fv = re.compile("^\s*FW\sPackage\sBuild:\s(.*)$")
            _ADP_OUT = Command["ADP_OUT"] % (cli, adapter)
            fw_version = get_func_value(_ADP_OUT, re_fv)
            re_pn = re.compile("^\s*Product\sName\s*:\s(.*)$")
            product_name = get_func_value(_ADP_OUT, re_pn)

        _LDS_NUM = Command["LDS_NUM"] % (cli, adapter)
        c = re.compile(".*Number\sof\sVirtual\sDrives\sConfigured\son\sAdapter\s%s:\s(\d+)" % adapter);
        number_of_lds = get_func_value(_LDS_NUM, c)
        if number_of_lds != None:
            number_of_lds = int(number_of_lds)
        elif number_of_lds == 0:
            print "No virtual disks found on adapter %s\n" % adapter;
            continue
        else:
            pass
            print number_of_lds

        # --------------virture driver --------------------
        _VD_LIST = Command["VD_LIST"] % (cli, adapter)
        re_d = re.compile("^\s*Virtual\sDrive:\s(\d+)\s.*$")
        re_vd_state = re.compile("^State\s+:\s(.*)$")
        re_vd_size = re.compile("^Size\s+:\s(\d+\.\d+\s..)")
        VD_LIST = get_metric_value(_VD_LIST)
        for _i in VD_LIST:
            _b = re_d.match(_i)
            if _b:
                vdrive_id = _b.group(1)
                # print "vdrive_id",vdrive_id
                continue
            _b = re_vd_state.match(_i)
            if _b:
                vdstate = _b.group(1)
                if vdstate == 'Optimal':
                    vdstate = '1'
                else:
                    vdstate = '0'
                # print "vdstate",vdstate
                # _key1="hw.raid.logical_disk.vd_size"
                _key2 = "hw.raid.logical_disk.vd_state"
                _tags = "adapter_id=%s,vdrive_id=%s" % (adapter, vdrive_id)
                # get_metric_dict(_key1,vdsize,_tags)
                get_metric_dict(_key2, vdstate, _tags)
                continue
            _b = re_vd_size.match(_i)
            if _b:
                vdsize = _b.group(1)
                # print "vdsize",vdsize
                continue

        # ------------BBU-----------
        _BBU_INFO = Command["BBU_INFO"] % (cli, adapter)
        # print _BBU_INFO
        re_e = re.compile(".*Get BBU Status Failed.*")
        BBU_INFO = get_metric_value(_BBU_INFO)
        for _i in BBU_INFO:
            if re_e.match(_i):
                pass

        com = "-GetBbuStatus"
        _BBU_OUT = Command["BBU_OUT"] % (cli, com, adapter)
        re_bbu = re.compile("Battery State\s*:\s(.*)$")
        bbu_state = get_func_value(_BBU_OUT, re_bbu)
        if bbu_state == 'Optimal':
            bbu_state = '1'
        else:
            bbu_state = '0'
        com = "-GetBBUDesignInfo"
        _BBU_OUT = Command["BBU_OUT"] % (cli, com, adapter)
        re_bbu = re.compile(".*Design\sCapacity:\s(\d+)\smAh.*")
        design_capacity = get_func_value(_BBU_OUT, re_bbu)
        com = "-GetBBUCapacityInfo"
        _BBU_OUT = Command["BBU_OUT"] % (cli, com, adapter)
        re_bbu = re.compile("(.*Full\sCharge\sCapacity|.*Pack\senergy\s*):\s(\d+)\s(mAh|J).*")
        full_capacity = get_func_value(_BBU_OUT, re_bbu, 2)
        com = "-GetBBUCapacityInfo"
        _BBU_OUT = Command["BBU_OUT"] % (cli, com, adapter)
        re_bbu = re.compile(".*Absolute\sState\sof\scharge\s*:\s(\d+).*%")
        state_of_charge = get_func_value(_BBU_OUT, re_bbu)
        com = "-GetBBUDesignInfo"
        _BBU_OUT = Command["BBU_OUT"] % (cli, com, adapter)
        re_bbu = re.compile(".*Date\sof\sManufacture\s*:\s(.*)")
        date_manufactured = get_func_value(_BBU_OUT, re_bbu)
        # print bbu_state,design_capacity,full_capacity,state_of_charge,date_manufactured

        _tags = "adapter_id=%s" % (adapter)
        _key1 = "hw.raid.bbu.full_capacity"
        get_metric_dict(_key1, full_capacity, _tags)
        _key1 = "hw.raid.bbu.bbu_state"
        get_metric_dict(_key1, bbu_state, _tags)
        _key1 = "hw.raid.bbu.design_capacity"
        get_metric_dict(_key1, design_capacity, _tags)
        _key1 = "hw.raid.bbu.state_of_charge"
        get_metric_dict(_key1, state_of_charge, _tags)

        _PD_LIST = Command["PD_LIST"] % (cli, adapter)
        re_f = re.compile("^Enclosure\sDevice\sID:\s(\d+)$")
        re_g = re.compile("^\s*Enclosure\sDevice\sID:\sN\/A$")
        re_h = re.compile("^Slot\sNumber:\s(\d+)$")
        enclosure_id = -1
        PD_LIST = get_metric_value(_PD_LIST)
        for _i in PD_LIST:
            # print _i
            _b = re_f.match(_i)
            if _b:
                check_next_line = 1
                enclosure_id = _b.group(1)
            elif re_g.match(_i):
                # This can happen, if embedded raid controller is in use, there are drives and logical disks, but no enclosures
                # enclosure_id       = 2989; # 0xBAD, :( magic hack
                enclosure_id = ""  # 0xBAD, :( magic hack
                check_next_line = 1
            _b = re_h.match(_i)
            if _b:
                _pd_list_index = _b.group(1)
                _CLI_OUT = Command["CLI_OUT"] % (cli, enclosure_id, _pd_list_index, adapter)
                CLI_OUT = get_metric_value(_CLI_OUT)
                re_me = re.compile("^Media Error Count:\s(.*)")
                re_pe = re.compile("^Predictive Failure Count:\s(.*)")
                re_rs = re.compile("^Raw Size:\s+(\d+\.\d+\s..)")
                re_fs = re.compile("^Firmware state:\s(.*)")
                re_id = re.compile("^Inquiry Data:\s+(.*)")
                for _i in CLI_OUT:
                    _b = re_me.match(_i)
                    if _b:
                        media_errors = _b.group(1)
                        continue
                    _b = re_pe.match(_i)
                    if _b:
                        predictive_errors = _b.group(1)
                        continue
                    _b = re_rs.match(_i)
                    if _b:
                        raw_size = _b.group(1)
                        continue
                    _b = re_fs.match(_i)
                    if _b:
                        firmware_state = _b.group(1)
                        if firmware_state == 'Online, Spun Up':
                            firmware_state = '1'
                        elif "Hotspare" in firmware_state:
                            # print firmware_state
                            firmware_state = '1'
                        elif "Unconfigured(good)" in firmware_state:
                            firmware_state = '1'
                        else:
                            firmware_state = '0'
                        continue
                    _b = re_id.match(_i)
                    if _b:
                        inquiry_data = _b.group(1)
                        _tags = "adapter_id=%s,enclosure_=%s,pd_id=%s" % (adapter, enclosure_id, _pd_list_index)
                        _key1 = "hw.raid.physical_disk.media_errors"
                        get_metric_dict(_key1, media_errors, _tags)
                        _key1 = "hw.raid.physical_disk.predictive_errors"
                        get_metric_dict(_key1, predictive_errors, _tags)
                        _key1 = "hw.raid.physical_disk.firmware_state"
                        get_metric_dict(_key1, firmware_state, _tags)

    print json.dumps(payload)


if __name__ == '__main__':
    main()
