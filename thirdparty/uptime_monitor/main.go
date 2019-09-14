//just for linux
//create by jinlong
package main

import(
	"syscall"
	"time"
	"encoding/json"
	"fmt"
)

func GetEndPoint() string {
	c := ParseConfig("/usr/local/open-falcon/agent/cfg.json")
	return c.Hostname
}

func GetUpTime() int64 {
   	si := &syscall.Sysinfo_t{}
	err := syscall.Sysinfo(si)
	if err != nil{
		//log.Print("get systime uptime failed")
		return 0
	}
	return si.Uptime
}

func GetTimeStamp() int64 {
	t := time.Now()
	return t.Unix()
}

func main() {
	var metric []*Metric
	endpoint := "hostname"
	value := GetUpTime()
	timestamp := GetTimeStamp()
	m := NewMetric(endpoint, value, timestamp)
	metric = append(metric, m)
	e, err := json.Marshal(metric)
	if err != nil {
		//log.Println("json marshal:", err)

	}
	fmt.Println(string(e))

}
