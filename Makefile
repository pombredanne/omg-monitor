build:
	docker build -t omg .

run:
	docker run -it -e DYNAMIC=true -e TAIL=true -p 8080:8080 -p 5000:5000 omg

rebuild: build run


shell: build
	docker run -it -e DYNAMIC=true -e TAIL=true -p 8080:8080 -p 5000:5000 --entrypoint '/bin/bash' omg 
