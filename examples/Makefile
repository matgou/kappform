###########################################################
# Makefile
# 
#  Organise build and dependancy
###########################################################

all: clean build install

build:
	
test:

install: AWS_BucketS3/main.tf AWS_BucketS3/model.yaml
	kubectl apply -f AWS_BucketS3/model.yaml

clean: 
	- kubectl delete -f AWS_BucketS3/model.yaml

.PHONY: all