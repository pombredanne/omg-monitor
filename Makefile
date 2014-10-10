build:
	docker build -t omg .

# this runs the app in dynamic monitor mode - listing for input on 8080. 
run:
	docker run -it -e DYNAMIC=true -e TAIL=true -p 8080:8080 -p 5000:5000 omg

rebuild: build run


# Need to shell in to dig around? here you go.
shell: build
	docker run -it -e DYNAMIC=true -e TAIL=true -p 8080:8080 -p 5000:5000 --entrypoint '/bin/bash' omg 
