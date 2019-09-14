#!/bin/env python
# -*- coding:utf-8 -*-
import json
import socket
import requests
import time
import platform
from requests.auth import HTTPBasicAuth

__author__ = 'jinlong'



ENDPOINT = None
IP = None
STEP = 60
PORT =  15672
USER = ""
PASSWORD = ""
FALCON_AGENT_URL = "http://127.0.0.1:8899/v1/push"

class RabbitmqMonitor(object):
    keys = ('messages_ready', 'messages_unacknowledged')
    rates = ('ack', 'deliver', 'deliver_get', 'publish')
    ts = int(time.time())
    step = 60

    def __init__(self, endpoint, ip, port, user, password, falcon_url):
        self.endpoint = endpoint
        self.ip = '127.0.0.1'
        self.port = port
        self.user = user
        self.password = password
        self.falcon_url = falcon_url
        self.auth = HTTPBasicAuth(self.user, self.password)

    def call_api(self, path):
        """
        调用rabbitmq api
        :param path: vhosts 方便以后拓展
        :return:
        """
        # print 'http://{0}:{1}/api/{2}'.format(self.ip, self.port, path)
        response = requests.get('http://{0}:{1}/api/{2}'.format(self.ip, self.port, path), auth=self.auth)
        if response.status_code == 200:
            #print response.json()
            return response.json()

        raise Exception("rabbit mq http api server error")

    def monitor_vhosts(self):
        try:
            data = self.call_api("vhosts")
            print data
        except Exception, e:
            print e
            return

        metric = self.__parse_data(data)
        print metric
        self.send_2_stdout(metric)

    def list_queues(self, filters=None):
        '''
        List all of the RabbitMQ queues, filtered against the filters provided
        in .rab.auth. See README.md for more information.
        '''
        queues = []
        if not filters:
            filters = [{}]
        for queue in self.call_api('queues'):
            for _filter in filters:
                check = [(x, y) for x, y in queue.items() if x in _filter]
                shared_items = set(_filter.items()).intersection(check)
                if len(shared_items) == len(_filter):
                    element = {'vhost': queue['vhost'],
                               'queue': queue['name']}
                    queues.append(element)
                    break
        self.__parse_queue_data(queues)



    def __parse_queue_data(self, queues):
        """
        [{'vhost': 'a', 'queue': 'b'}, {'vhost':'a', 'c'}]
        :param queues:
        :return:
        """
        metrics = []
        for queue in queues:
            response = requests.get('http://{0}:{1}/api/queues/{2}/{3}'.format(self.ip, self.port, queue.get('vhost'), queue.get('queue')), auth=self.auth)
            if response.status_code == 200:
                messages = response.json().get('messages')
                vhost = queue.get("vhost")
                queue_name = queue.get("queue")
                q = {"endpoint": self.endpoint, 'timestamp': self.ts, 'step': self.step, 'counterType': "GAUGE",
                 'metric': 'rabbitmq.messages.length', 'tags': 'vhost={0},queue={1}'.format(vhost, queue_name), 'value': messages}
                metrics.append(q)

        ##################### network parttitions #####################################
        result = requests.get('http://{0}:{1}/api/nodes'.format(self.ip, self.port), auth=self.auth)
        result = [network['partitions']  for network in json.loads(result.content) if network['partitions']]

        if len(result) != 0:
            m = {"endpoint": self.endpoint, 'timestamp': self.ts, 'step': self.step, 'counterType': "GAUGE",
               'metric': 'rabbitmq.network', 'tags': 'network_monitor', 'value': 1}
            metrics.append(m)
        else:
            m = {"endpoint": self.endpoint, 'timestamp': self.ts, 'step': self.step, 'counterType': "GAUGE",
               'metric': 'rabbitmq.network', 'tags': 'network_monitor', 'value': 0}
            metrics.append(m)
        ##################### network parttitions #####################################
        
        if metrics:
            self.send_2_stdout(metrics)

    def __parse_data(self, data):
        p = []
        for queue in data:
            # ready and unack
            msg_total = 0
            for key in self.keys:
                print key
                q = {"endpoint": self.endpoint, 'timestamp': self.ts, 'step': self.step, 'counterType': "GAUGE",
                     'metric': 'rabbitmq.%s' % key, 'tags': 'collect_type=plugins,name=%s,%s' % (queue['name'], ""),
                     'value': int(queue[key])}
                msg_total += q['value']
                p.append(q)

            # total
            q = {"endpoint": self.endpoint, 'timestamp': self.ts, 'step': self.step, 'counterType': "GAUGE",
                 'metric': 'rabbitmq.messages_total', 'tags': 'collect_type=plugins,name=%s,%s' % (queue['name'], ""), 'value': msg_total}
            p.append(q)

            # rates
            for rate in self.rates:
                q = {"endpoint": self.endpoint, 'timestamp': self.ts, 'step': self.step, 'counterType': "GAUGE",
                     'metric': 'rabbitmq.%s_rate' % rate, 'tags': 'collect_type=plugins,name=%s,%s' % (queue['name'], "")}
                try:
                    q['value'] = int(queue['message_stats']["%s_details" % rate]['rate'])
                except Exception:
                    q['value'] = 0
                p.append(q)
        return p

    def send_2_falcon(self, metric):
        requests.post(self.falcon_url, json=metric)

    def send_2_stdout(self, metric):
        print json.dumps(metric)


def main():
    if platform.system() != 'Linux':
        return

    global ENDPOINT
    global IP


    ENDPOINT = "hostname"
    IP = "ip"
    monitor = RabbitmqMonitor(ENDPOINT, IP, PORT, USER, PASSWORD,
                              FALCON_AGENT_URL)
    monitor.list_queues()


if __name__ == "__main__":
    main()
