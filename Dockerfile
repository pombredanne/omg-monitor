FROM cloudwalk/nupic

MAINTAINER Allan Costa <allan@cloudwalk.io>

# Install redis, redis-py and go
RUN \
    pip install redis;\

    wget http://go.googlecode.com/files/go1.1.2.linux-amd64.tar.gz;\
    tar -C /usr/local -xzf go1.1.2.linux-amd64.tar.gz;\
    rm go1.1.2.linux-amd64.tar.gz;\
    
    wget http://download.redis.io/releases/redis-2.6.16.tar.gz;\
    tar -xzf redis-2.6.16.tar.gz;\
    cd redis-2.6.16;\
    make;\
    rm ../redis-2.6.16.tar.gz;
#RUN

# Install librato
RUN pip install librato-metrics

# Add redis and go to path
ENV GOPATH /home/docker/go
ENV PATH /home/docker/redis-2.6.16/src:/usr/local/go/bin:$PATH

# Install go packages
RUN \
    go get github.com/codegangsta/martini;\
    go get github.com/garyburd/redigo/redis;
#RUN

# Copy omg-monitor directory
ADD startup.sh /home/docker/omg-monitor/startup.sh
ADD monitor/ /home/docker/omg-monitor/monitor
ADD server/ /home/docker/omg-monitor/server

# Build Go server's binary
RUN \
    cd /home/docker/omg-monitor/server;\
    go build;
#RUN

EXPOSE 5000

# Set directory for logs
ENV LOG_DIR /var/log/docker/monitor

WORKDIR /home/docker/omg-monitor/

ENTRYPOINT ["./startup.sh"]
