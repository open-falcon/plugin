package main

import (
	"encoding/json"
	"log"
	"github.com/toolkits/file"
)

type Metric struct {
	EndPoint    string     `json:"endpoint"`
	Tags        string     `json:"tags"`
	Timestamp   int64      `json:"timestamp"`
	Metric      string     `json:"metric"`
	Value       int64        `json:"value"`
	CounterType string     `json:"counterType"`
	Step        int        `json:"step"`
}

func NewMetric(endpoint string, value int64, timestamp int64) *Metric {
	m := &Metric{
		EndPoint: endpoint,
		Metric: "system.uptime",
		Tags: "",
		Timestamp: timestamp,
		Value: value,
		CounterType: "GAUGE",
		Step: 60,
	}
	return m
}

type PluginConfig struct {
	Enabled bool   `json:"enabled"`
	Dir     string `json:"dir"`
	Git     string `json:"git"`
	LogDir  string `json:"logs"`
}

type HeartbeatConfig struct {
	Enabled  bool   `json:"enabled"`
	Addr     string `json:"addr"`
	Interval int    `json:"interval"`
	Timeout  int    `json:"timeout"`
}

type TransferConfig struct {
	Enabled  bool     `json:"enabled"`
	Addrs    []string `json:"addrs"`
	Interval int      `json:"interval"`
	Timeout  int      `json:"timeout"`
}

type HttpConfig struct {
	Enabled  bool   `json:"enabled"`
	Listen   string `json:"listen"`
	Backdoor bool   `json:"backdoor"`
}

type CollectorConfig struct {
	IfacePrefix []string `json:"ifacePrefix"`
}

type GlobalConfig struct {
	Debug         bool             `json:"debug"`
	Hostname      string           `json:"hostname"`
	IP            string           `json:"ip"`
	Plugin        *PluginConfig    `json:"plugin"`
	Heartbeat     *HeartbeatConfig `json:"heartbeat"`
	Transfer      *TransferConfig  `json:"transfer"`
	Http          *HttpConfig      `json:"http"`
	Collector     *CollectorConfig `json:"collector"`
	IgnoreMetrics map[string]bool  `json:"ignore"`
}

func ParseConfig(cfg string) *GlobalConfig{
	if cfg == "" {
		log.Fatalln("use -c to specify configuration file")
	}

	if !file.IsExist(cfg) {
		log.Fatalln("config file:", cfg, "is not existent. maybe you need `mv cfg.example.json cfg.json`")
	}

	configContent, err := file.ToTrimString(cfg)
	if err != nil {
		log.Fatalln("read config file:", cfg, "fail:", err)
	}

	var c GlobalConfig
	err = json.Unmarshal([]byte(configContent), &c)
	if err != nil {
		log.Fatalln("parse config file:", cfg, "fail:", err)
	}

	return &c
}