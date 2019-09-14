#! /bin/env python
# coding=utf8

import sys
import time
import json
import platform
import pymongo
from pymongo import MongoClient


class MongodbMonitor(object):

    def mongodb_connect(self, host=None, port=None, user=None, password=None):
        try:
            conn = MongoClient(host, port, serverSelectionTimeoutMS=1000)  # conntion timeout 1 sec.

            if user and password:
                db_admin = conn["admin"]
                if not db_admin.authenticate(user, password):
                    pass;
            conn.server_info()
        except:
            e = sys.exc_info()[0]
            return e, None

        return 0, conn

    # data node(1): standalone, replset primary, replset secondary. mongos(2), mongoConfigSrv(3)
    def get_mongo_role(self, conn):

        mongo_role = 1
        conn.server_info()
        if (conn.is_mongos):
            mongo_role = 2
        elif ("chunks" in conn.get_database(
                "config").collection_names()):  # Role is a config servers?  not mongos and has config.chunks collections. it's a config server.
            mongo_role = 3
        return mongo_role

    def get_mongo_monitor_data(self, conn):

        mongo_monitor_dict = {}
        mongo_monitor_dict["mongo_local_alive"] = 1  # mongo local alive metric for all nodes.
        mongo_role = self.get_mongo_role(conn)

        if (mongo_role == 1):
            mongodb_role, serverStatus_dict = self.serverStatus(conn)
            mongo_monitor_dict.update(serverStatus_dict)
            repl_status_dict = {}
            if (mongodb_role == "master" or mongodb_role == "secondary"):
                repl_status_dict = self.repl_status(conn)
                mongo_monitor_dict.update(repl_status_dict)
            else:
                print "this is standalone node"
        elif (mongo_role == 2):  # mongos
            shards_dict = self.shard_status(conn)
            mongo_monitor_dict.update(shards_dict)
        return mongo_monitor_dict

    def serverStatus(self, connection):

        serverStatus = connection.admin.command(pymongo.son_manipulator.SON([('serverStatus', 1)]))

        mongodb_server_dict = {}  # mongodb server status metric for upload to falcon

        mongo_version = serverStatus["version"]
        # uptime metric
        mongodb_server_dict["uptime"] = int(serverStatus["uptime"])

        # asserts section metrics
        mongo_asserts = serverStatus["asserts"]
        for asserts_key in mongo_asserts.keys():
            asserts_key_name = "asserts_" + asserts_key
            mongodb_server_dict[asserts_key_name] = mongo_asserts[asserts_key]

        ### "extra_info" section metrics: page_faults.  falcon counter type.
        if serverStatus.has_key("extra_info"):
            mongodb_server_dict["page_faults"] = serverStatus["extra_info"]["page_faults"]

        ### "connections" section metrics
        current_conn = serverStatus["connections"]["current"]
        available_conn = serverStatus["connections"]["available"]

        mongodb_server_dict["connections_current"] = current_conn
        mongodb_server_dict["connections_available"] = available_conn

        # mongodb connection used percent
        mongodb_server_dict["connections_used_percent"] = int((current_conn / (current_conn + available_conn) * 100))

        # total created from mongodb started.  COUNTER metric
        mongodb_server_dict["connections_totalCreated"] = serverStatus["connections"]["totalCreated"]

        #  "globalLock" currentQueue

        mongodb_server_dict["globalLock_currentQueue_total"] = serverStatus["globalLock"]["currentQueue"]["total"]
        mongodb_server_dict["globalLock_currentQueue_readers"] = serverStatus["globalLock"]["currentQueue"]["readers"]
        mongodb_server_dict["globalLock_currentQueue_writers"] = serverStatus["globalLock"]["currentQueue"]["writers"]

        # "locks" section, Changed in version 3.0
        if serverStatus.has_key("locks") and mongo_version > "3.0":
            locks_dict_keys = serverStatus["locks"].keys()
            for lock_scope in locks_dict_keys:  # Global, Database,Collection,Oplog
                for lock_metric in serverStatus["locks"][lock_scope]:
                    for lock_type in serverStatus["locks"][lock_scope][lock_metric]:

                        if lock_type == "R":
                            lock_name = "Slock"
                        elif lock_type == "W":
                            lock_name = "Xlock"
                        elif lock_type == "r":
                            lock_name = "ISlock"
                        elif lock_type == "w":
                            lock_name = "IXlock"
                        lock_metric_key = "locks_" + lock_scope + "_" + lock_metric + "_" + lock_name
                        mongodb_server_dict[lock_metric_key] = serverStatus["locks"][lock_scope][lock_metric][lock_type]

        # "network" section metrics: bytesIn, bytesOut, numRequests;  counter type
        if serverStatus.has_key("network"):
            for network_metric in serverStatus["network"].keys():
                network_metric_key = "network_" + network_metric  # network metric key for upload
                mongodb_server_dict[network_metric_key] = serverStatus["network"][network_metric]

        ### "opcounters" section metrics:　insert, query, update, delete, getmore, command. couter type
        if serverStatus.has_key("opcounters"):
            for opcounters_metric in serverStatus["opcounters"].keys():
                opcounters_metric_key = "opcounters_" + opcounters_metric
                mongodb_server_dict[opcounters_metric_key] = serverStatus["opcounters"][opcounters_metric]

        ### "opcountersRepl" section metrics: insert, query, update, delete, getmore, command. couter type
        if serverStatus.has_key("opcountersRepl"):
            for opcountersRepl_metric in serverStatus["opcountersRepl"].keys():
                opcountersRepl_metric_key = "opcountersRepl_" + opcountersRepl_metric
                mongodb_server_dict[opcountersRepl_metric_key] = serverStatus["opcounters"][opcountersRepl_metric]

        ### "mem" section metrics:
        if serverStatus.has_key("mem"):
            for mem_metric in serverStatus["mem"].keys():
                mem_metric_key = "mem_" + mem_metric
                if (mem_metric in ["bits", "supported"]):
                    mongodb_server_dict[mem_metric_key] = serverStatus["mem"][mem_metric]
                else:
                    mongodb_server_dict[mem_metric_key] = serverStatus["mem"][mem_metric] * 1024 * 1024

        ### "dur" section metrics:
        if serverStatus.has_key("dur"):
            mongodb_server_dict["dur_journaledBytes"] = serverStatus["dur"]["journaledMB"] * 1024 * 1024
            mongodb_server_dict["dur_writeToDataFilesBytes"] = serverStatus["dur"]["writeToDataFilesMB"] * 1024 * 1024
            mongodb_server_dict["dur_commitsInWriteLock"] = serverStatus["dur"]["commitsInWriteLock"]

        ### "repl" section
        mongodb_role = ""
        if (serverStatus.has_key("repl") and serverStatus["repl"].has_key("secondary")):
            if serverStatus["repl"]["ismaster"]:
                mongodb_role = "master"
            if serverStatus["repl"]["secondary"]:
                mongodb_role = "secondary"
        else:  # not Replica sets mode
            mongodb_role = "standalone"

        ### "backgroundFlushing" section metrics, only for MMAPv1
        if serverStatus.has_key("backgroundFlushing"):
            for bgFlush_metric in serverStatus["backgroundFlushing"].keys():
                if bgFlush_metric != "last_finished":  # discard last_finished metric
                    bgFlush_metric_key = "backgroundFlushing_" + bgFlush_metric
                    mongodb_server_dict[bgFlush_metric_key] = serverStatus["backgroundFlushing"][bgFlush_metric]

        ### cursor from "metrics" section
        if serverStatus.has_key("metrics") and serverStatus["metrics"].has_key("cursor"):
            cursor_status = serverStatus["metrics"]["cursor"]
            mongodb_server_dict["cursor_timedOut"] = cursor_status["timedOut"]
            mongodb_server_dict["cursor_open_noTimeout"] = cursor_status["open"]["noTimeout"]
            mongodb_server_dict["cursor_open_pinned"] = cursor_status["open"]["pinned"]
            mongodb_server_dict["cursor_open_total"] = cursor_status["open"]["total"]

        ### "wiredTiger" section
        if serverStatus.has_key("wiredTiger"):
            serverStatus_wt = serverStatus["wiredTiger"]

            # cache
            wt_cache = serverStatus_wt["cache"]
            mongodb_server_dict["wt_cache_used_total_bytes"] = wt_cache["bytes currently in the cache"]
            mongodb_server_dict["wt_cache_dirty_bytes"] = wt_cache["tracked dirty bytes in the cache"]
            mongodb_server_dict["wt_cache_readinto_bytes"] = wt_cache["bytes read into cache"]
            mongodb_server_dict["wt_cache_writtenfrom_bytes"] = wt_cache["bytes written from cache"]

            # concurrentTransactions
            wt_concurrentTransactions = serverStatus_wt["concurrentTransactions"]
            mongodb_server_dict["wt_concurrentTransactions_write"] = wt_concurrentTransactions["write"]["available"]
            mongodb_server_dict["wt_concurrentTransactions_read"] = wt_concurrentTransactions["read"]["available"]

            # "block-manager" section
            wt_block_manager = serverStatus_wt["block-manager"]
            mongodb_server_dict["wt_bm_bytes_read"] = wt_block_manager["bytes read"]
            mongodb_server_dict["wt_bm_bytes_written"] = wt_block_manager["bytes written"]
            mongodb_server_dict["wt_bm_blocks_read"] = wt_block_manager["blocks read"]
            mongodb_server_dict["wt_bm_blocks_written"] = wt_block_manager["blocks written"]

        ### "rocksdb" engine
        if serverStatus.has_key("rocksdb"):
            serverStatus_rocksdb = serverStatus["rocksdb"]

            mongodb_server_dict["rocksdb_num_immutable_mem_table"] = serverStatus_rocksdb["num-immutable-mem-table"]
            mongodb_server_dict["rocksdb_mem_table_flush_pending"] = serverStatus_rocksdb["mem-table-flush-pending"]
            mongodb_server_dict["rocksdb_compaction_pending"] = serverStatus_rocksdb["compaction-pending"]
            mongodb_server_dict["rocksdb_background_errors"] = serverStatus_rocksdb["background-errors"]
            mongodb_server_dict["rocksdb_num_entries_active_mem_table"] = serverStatus_rocksdb[
                "num-entries-active-mem-table"]
            mongodb_server_dict["rocksdb_num_entries_imm_mem_tables"] = serverStatus_rocksdb[
                "num-entries-imm-mem-tables"]
            mongodb_server_dict["rocksdb_num_snapshots"] = serverStatus_rocksdb["num-snapshots"]
            mongodb_server_dict["rocksdb_oldest_snapshot_time"] = serverStatus_rocksdb["oldest-snapshot-time"]
            mongodb_server_dict["rocksdb_num_live_versions"] = serverStatus_rocksdb["num-live-versions"]
            mongodb_server_dict["rocksdb_total_live_recovery_units"] = serverStatus_rocksdb["total-live-recovery-units"]

        ### "PerconaFT" engine
        if serverStatus.has_key("PerconaFT"):
            serverStatus_PerconaFT = serverStatus["PerconaFT"]

            mongodb_server_dict["PerconaFT_log_count"] = serverStatus_PerconaFT["log"]["count"]
            mongodb_server_dict["PerconaFT_log_time"] = serverStatus_PerconaFT["log"]["time"]
            mongodb_server_dict["PerconaFT_log_bytes"] = serverStatus_PerconaFT["log"]["bytes"]

            mongodb_server_dict["PerconaFT_fsync_count"] = serverStatus_PerconaFT["fsync"]["count"]
            mongodb_server_dict["PerconaFT_fsync_time"] = serverStatus_PerconaFT["fsync"]["time"]

            ### cachetable
            PerconaFT_cachetable = serverStatus_PerconaFT["cachetable"]
            mongodb_server_dict["PerconaFT_cachetable_size_current"] = PerconaFT_cachetable["size"]["current"]
            mongodb_server_dict["PerconaFT_cachetable_size_writing"] = PerconaFT_cachetable["size"]["writing"]
            mongodb_server_dict["PerconaFT_cachetable_size_limit"] = PerconaFT_cachetable["size"]["limit"]

            ### PerconaFT checkpoint
            PerconaFT_checkpoint = serverStatus_PerconaFT["checkpoint"]
            mongodb_server_dict["PerconaFT_checkpoint_count"] = PerconaFT_checkpoint["count"]
            mongodb_server_dict["PerconaFT_checkpoint_time"] = PerconaFT_checkpoint["time"]

            mongodb_server_dict["PerconaFT_checkpoint_write_nonleaf_count"] = PerconaFT_checkpoint["write"]["nonleaf"][
                "count"]
            mongodb_server_dict["PerconaFT_checkpoint_write_nonleaf_time"] = PerconaFT_checkpoint["write"]["nonleaf"][
                "time"]
            mongodb_server_dict["PerconaFT_checkpoint_write_nonleaf_bytes_compressed"] = \
                PerconaFT_checkpoint["write"]["nonleaf"]["bytes"]["compressed"]
            mongodb_server_dict["PerconaFT_checkpoint_write_nonleaf_bytes_uncompressed"] = \
                PerconaFT_checkpoint["write"]["nonleaf"]["bytes"]["uncompressed"]
            mongodb_server_dict["PerconaFT_checkpoint_write_leaf_count"] = PerconaFT_checkpoint["write"]["leaf"][
                "count"]
            mongodb_server_dict["PerconaFT_checkpoint_write_leaf_time"] = PerconaFT_checkpoint["write"]["leaf"]["time"]
            mongodb_server_dict["PerconaFT_checkpoint_write_leaf_bytes_compressed"] = \
                PerconaFT_checkpoint["write"]["leaf"]["bytes"]["compressed"]
            mongodb_server_dict["PerconaFT_checkpoint_write_leaf_bytes_uncompressed"] = \
                PerconaFT_checkpoint["write"]["leaf"]["bytes"]["uncompressed"]

            ### serializeTime

            for serializeTime_item in serverStatus_PerconaFT["serializeTime"]:
                prefix = "PerconaFT_serializeTime_" + serializeTime_item
                for serializeTime_key in serverStatus_PerconaFT["serializeTime"][serializeTime_item]:
                    key_name = prefix + "_" + serializeTime_key
                    mongodb_server_dict[key_name] = serverStatus_PerconaFT["serializeTime"][serializeTime_item][
                        serializeTime_key]

            ### PerconaFT  compressionRatio
            for compressionRatio_item in serverStatus_PerconaFT["compressionRatio"]:
                key_name = "PerconaFT_compressionRatio_" + compressionRatio_item
                mongodb_server_dict[key_name] = serverStatus_PerconaFT["compressionRatio"][compressionRatio_item]

        return (mongodb_role, mongodb_server_dict)

    def repl_status(self, connection):
        replStatus = connection.admin.command("replSetGetStatus")
        repl_status_dict = {}  # repl set metric dict

        # myState "1" for PRIMARY , "2" for  SECONDARY, "3":
        repl_status_dict["repl_myState"] = replStatus["myState"]

        repl_status_members = replStatus["members"]

        master_optime = 0  # Master oplog ops time
        myself_optime = 0  # SECONDARY oplog ops time

        for repl_member in repl_status_members:
            if repl_member.has_key("self") and repl_member["self"]:
                repl_status_dict["repl_health"] = repl_member["health"]
                repl_status_dict["repl_optime"] = repl_member["optime"].time
                if repl_member.has_key("repl_electionTime"):
                    repl_status_dict["repl_electionTime"] = repl_member["electionTime"].time
                if repl_member.has_key("repl_configVersion"):
                    repl_status_dict["repl_configVersion"] = repl_member["configVersion"]
                myself_optime = repl_member["optime"].time
            if (replStatus["myState"] == 2 and repl_member["state"] == 1):  # CONDARY ,get repl lag
                master_optime = repl_member["optime"].time
        if replStatus["myState"] == 2:
            repl_status_dict["repl_lag"] = master_optime - myself_optime

        ### oplog window  hours

        oplog_collection = connection["local"]["oplog.rs"]

        oplog_tFirst = oplog_collection.find({}, {"ts": 1}).sort('$natural', pymongo.ASCENDING).limit(1).next()
        oplog_tLast = oplog_collection.find({}, {"ts": 1}).sort('$natural', pymongo.DESCENDING).limit(1).next()

        oplogrs_collstats = connection["local"].command("collstats", "oplog.rs")

        window_multiple = 1  ##oplog.rs collections is not full
        if oplogrs_collstats.has_key("maxSize"):
            window_multiple = oplogrs_collstats["maxSize"] / (
                    oplogrs_collstats["count"] * oplogrs_collstats["avgObjSize"])
        else:
            window_multiple = oplogrs_collstats["storageSize"] / (
                    oplogrs_collstats["count"] * oplogrs_collstats["avgObjSize"])

        # oplog_window  .xx hours
        oplog_window = round((oplog_tLast["ts"].time - oplog_tFirst["ts"].time) / 3600.0, 2) * window_multiple  # full

        repl_status_dict["repl_oplog_window"] = oplog_window

        return repl_status_dict

    # only for mongos node
    def shard_status(self, conn):

        config_db = conn["config"]

        settings_col = config_db["settings"]

        balancer_doc = settings_col.find_one({'_id': 'balancer'})

        shards_dict = {}
        if balancer_doc is None:
            shards_dict["shards_BalancerState"] = 1
        elif balancer_doc["stopped"]:
            shards_dict["shards_BalancerState"] = 0
        else:
            shards_dict["shards_BalancerState"] = 1

        # shards_activeWindow metric,0: without setting, 1:setting
        # shards_activeWindow_start  metric,  { "start" : "23:30", "stop" : "6:00" } :  23.30 for  23:30
        # shards_activeWindow_stop metric

        if balancer_doc is None:
            shards_dict["shards_activeWindow"] = 0

        elif balancer_doc.has_key("activeWindow"):
            shards_dict["shards_activeWindow"] = 1
            if balancer_doc["activeWindow"].has_key("start"):
                window_start = balancer_doc["activeWindow"]["start"]
                shards_dict["shards_activeWindow_start"] = window_start.replace(":", ".")

            if balancer_doc["activeWindow"].has_key("stop"):
                window_stop = balancer_doc["activeWindow"]["stop"]
                shards_dict["shards_activeWindow_stop"] = window_stop.replace(":", ".")

        # shards_chunkSize metric
        chunksize_doc = settings_col.find_one({"_id": "chunksize"})
        if chunksize_doc is not None:
            shards_dict["shards_chunkSize"] = chunksize_doc["value"]

        # shards_isBalancerRunning metric
        locks_col = config_db["locks"]
        balancer_lock_doc = locks_col.find_one({'_id': 'balancer'})

        if balancer_lock_doc is None:
            print "config.locks collection empty or missing. be sure you are connected to a mongos"
            shards_dict["shards_isBalancerRunning"] = 0
        elif balancer_lock_doc["state"] > 0:
            shards_dict["shards_isBalancerRunning"] = 1
        else:
            shards_dict["shards_isBalancerRunning"] = 0

        # shards_size metric

        shards_col = config_db["shards"]
        shards_dict["shards_size"] = shards_col.count()

        # shards_mongosSize metric
        mongos_col = config_db["mongos"]
        shards_dict["shards_mongosSize"] = mongos_col.count()

        return shards_dict


# all falcon counter type metrics list

mongodb_counter_metric = [
    "asserts_msg",
    "asserts_regular",
    "asserts_rollovers",
    "asserts_user",
    "asserts_warning",
    "page_faults",
    "connections_totalCreated",
    "locks_Global_acquireCount_ISlock",
    "locks_Global_acquireCount_IXlock",
    "locks_Global_acquireCount_Slock",
    "locks_Global_acquireCount_Xlock",
    "locks_Global_acquireWaitCount_ISlock",
    "locks_Global_acquireWaitCount_IXlock",
    "locks_Global_timeAcquiringMicros_ISlock",
    "locks_Global_timeAcquiringMicros_IXlock",
    "locks_Database_acquireCount_ISlock",
    "locks_Database_acquireCount_IXlock",
    "locks_Database_acquireCount_Slock",
    "locks_Database_acquireCount_Xlock",
    "locks_Collection_acquireCount_ISlock",
    "locks_Collection_acquireCount_IXlock",
    "locks_Collection_acquireCount_Xlock",
    "opcounters_command",
    "opcounters_insert",
    "opcounters_delete",
    "opcounters_update",
    "opcounters_query",
    "opcounters_getmore",
    "opcountersRepl_command",
    "opcountersRepl_insert",
    "opcountersRepl_delete",
    "opcountersRepl_update",
    "opcountersRepl_query",
    "opcountersRepl_getmore",
    "network_bytesIn",
    "network_bytesOut",
    "network_numRequests",
    "backgroundFlushing_flushes",
    "backgroundFlushing_last_ms",
    "cursor_timedOut",
    "wt_cache_readinto_bytes",
    "wt_cache_writtenfrom_bytes",
    "wt_bm_bytes_read",
    "wt_bm_bytes_written",
    "wt_bm_blocks_read",
    "wt_bm_blocks_written"]

if platform.system() != 'Linux':
    sys.exit(0)


mongo_connect_host = '127.0.0.1'
mongodb_hostname = "hostname"
IP = "IP"
mongodb_items = [{"port": 27017, "user": "", "password": ""}]
ts = int(time.time())

for mongodb_ins in mongodb_items:

    mongodb_monitor = MongodbMonitor()

    mongodb_tag = "mongo=" + str(mongodb_ins["port"])
    mongodb_tag = 'collect_type=plugin,' + mongodb_tag

    err, conn = mongodb_monitor.mongodb_connect(host=mongo_connect_host, port=mongodb_ins["port"],
                                                user=mongodb_ins["user"], password=mongodb_ins["password"])

    mongodb_upate_list = []
    if err != 0:
        key_item_dict = {"endpoint": mongodb_hostname, "metric": "mongo_local_alive", "tags": mongodb_tag,
                         "timestamp": ts, "value": 0, "step": 60, "counterType": "GAUGE"}
        mongodb_upate_list.append(key_item_dict)
        print json.dumps(mongodb_upate_list)
        continue  # The instance is dead. upload the "mongo_alive_local=0" key, then continue.

    mongodb_dict = mongodb_monitor.get_mongo_monitor_data(conn)
    mongodb_dict_keys = mongodb_dict.keys()

    for mongodb_metric in mongodb_dict_keys:

        if mongodb_metric in mongodb_counter_metric:
            key_item_dict = {"endpoint": mongodb_hostname, "metric": 'mongo.' + mongodb_metric, "tags": mongodb_tag,
                             "timestamp": ts, "value": mongodb_dict[mongodb_metric], "step": 60,
                             "counterType": "COUNTER"}
        else:
            key_item_dict = {"endpoint": mongodb_hostname, "metric": 'mongo.' + mongodb_metric, "tags": mongodb_tag,
                             "timestamp": ts, "value": mongodb_dict[mongodb_metric], "step": 60, "counterType": "GAUGE"}

        mongodb_upate_list.append(key_item_dict)
    print json.dumps(mongodb_upate_list)
