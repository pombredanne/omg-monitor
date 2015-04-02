build:
	docker build -t cloudwalk/monitor .

# this runs the app in dynamic monitor mode - listing for input on 8080.
run:
	docker run -e DYNAMIC=true -p 8080:8080 -p 5000:5000 cloudwalk/monitor

rebuild: build run

# Need to shell in to dig around? here you go.
shell: build
	docker run -it -e DYNAMIC=true -p 8080:8080 -p 5000:5000 --entrypoint '/bin/bash' cloudwalk/monitor

debug: build
	docker run -v $(PWD)/logs:/var/log/docker/monitor -e DYNAMIC=true -p 8080:8080 -p 5000:5000 cloudwalk/monitor
