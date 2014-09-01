package main

import (
    "github.com/codegangsta/martini"
    "github.com/garyburd/redigo/redis"
    "net/http"
    "encoding/json"
    "fmt"
    "strings"
    "strconv" 
    "log"
    "time"
)

type Monitors struct {
    Monitors []MonitorType `json:"monitors"`
}

type MonitorType struct {
    ID string `json:"id"`
    Name string `json:"name"`
    ValueLabel string `json:"value_label"`
    ValueUnit string `json:"value_unit"`
}

type Results struct {
    Results []ResultType `json:"results"`
}

type ResultType struct {
    Time int64 `json:"time"`
    Actual int64 `json:"actual"`
    Predicted int64 `json:"predicted"`
    Anomaly float64 `json:"anomaly"`
    Likelihood float64 `json:"likelihood"`
}

const (
        maxConnections = 5
        connectTimeout = time.Duration(10) * time.Second
        readTimeout = time.Duration(10) * time.Second
        writeTimeout = time.Duration(10) * time.Second
        server = "localhost:6379"
)

var redisPool = redis.NewPool(func() (redis.Conn, error) {
        c, err := redis.DialTimeout("tcp", server, connectTimeout, readTimeout, writeTimeout)
        if err != nil {
            fmt.Printf("redis.NewPool err=%s\n", err)
            return nil, err
        }

        return c, err
}, maxConnections)

// Return a JSON with the ids, names, value_label and value_unit for all monitors
func getJsonMonitors(redisResponse []interface{}) []byte {
    conn := redisPool.Get() // Redis connection to get the names for the ids

    monitors := make([]MonitorType, len(redisResponse))

    for k, _ := range redisResponse {
        v := ""
        redisResponse, _ = redis.Scan(redisResponse, &v)

        id := v[5:len(v)]

        // Get the name corresponding to the id
        name, errn := redis.String(conn.Do("GET", "name:" + id))
        for {
            if errn == nil { 
                break; 
                } else {
                    log.Printf("Redis error in GET name: %s\n", errn)
                    name, errn = redis.String(conn.Do("GET", "name:" + id))
                }
        }
  
        // Get the value_label corresponding to the id
        valueLabel, errvl := redis.String(conn.Do("GET", "value_label:" + id))
        for {
            if errvl == nil { 
                break; 
                } else {
                    log.Printf("Redis error in GET value_label: %s\n", errvl)
                    valueLabel, errvl = redis.String(conn.Do("GET", "value_label:" + id))
                }
        }

        // Get the value_unit corresponding to the id
        valueUnit, errvu := redis.String(conn.Do("GET", "value_unit:" + id))
        for {
            if errvu == nil { 
                break; 
                } else {
                    log.Printf("Redis error in GET value_unit: %s\n", errvu)
                    valueUnit, errvu = redis.String(conn.Do("GET", "value_unit:" + id))
                }
        }

        monitors[k] = MonitorType{id, name, valueLabel, valueUnit}
    }
    conn.Close()
    b,_ := json.MarshalIndent(Monitors{monitors}, "", "  ")
    return b
} 

// Return a JSON with the results
func getJsonResults(redisResponse []interface{}) []byte {
    results := make([]ResultType, len(redisResponse))

    for k, _ := range redisResponse {
        // oneResult holds one line of the list of results 
        v := ""
        redisResponse, _ = redis.Scan(redisResponse, &v)
        
        fields := strings.Split(v, ",")

        // Set the fields that will compose the ResultType object
        time, _ := strconv.ParseInt(fields[0], 10, 64)
        actual, _ := strconv.ParseInt(fields[1], 10, 64)
        predicted, _ := strconv.ParseInt(fields[2], 10, 64)
        anomaly, _ := strconv.ParseFloat(fields[3], 64)
        likelihood, _ := strconv.ParseFloat(fields[4], 64)

        results[k] = ResultType{time, actual, predicted, anomaly, likelihood}
    }

    b,_ := json.MarshalIndent(Results{results}, "", "  ")
    return b
} 

func main() {

    m := martini.Classic()

    // Handle the "/results" API method
    m.Get("/results/:check_id", func(params martini.Params, res http.ResponseWriter, req *http.Request) string {
        conn := redisPool.Get()
        
        // Parse the url to get the query paramenter named "limit" and convert to int
        limit, _ := strconv.ParseInt(req.URL.Query().Get("limit"),10, 64)

        // Query redis for the last "limit" results for the given "check_id"
        reply, err := redis.Values(conn.Do("LRANGE", "results:" + params["check_id"], -limit, -1))
        for {
            if err == nil { 
                break; 
                } else {
                    log.Printf("Redis error in LRANGE results: %s\n", err)
                    reply, err = redis.Values(conn.Do("LRANGE", "results:" + params["check_id"], -limit, -1))
                }
        }
        conn.Close()
        return string(getJsonResults(reply))
    })

    // Handle the "/monitors" API method
    m.Get("/monitors", func(params martini.Params) string {
        conn := redisPool.Get()

        // Query redis all the available "monitors"
        reply, err := redis.Values(conn.Do("KEYS", "name:*"))
        for {
            if err == nil { 
                break; 
                } else {
                    log.Printf("Redis error in KEYS name: %s\n", err)
                    reply, err = redis.Values(conn.Do("KEYS", "name:*"))
                }
        }
        conn.Close()
        return string(getJsonMonitors(reply))
    })

    fmt.Printf("[martini] Listening on port 5000\n")
    err := http.ListenAndServe("0.0.0.0:5000", m)
    if err != nil {
        fmt.Printf("Error: %s", err)
    }
}