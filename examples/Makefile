###########################################################
# Makefile
# 
#  Organise build and dependancy
###########################################################

all: clean build install

build:
	
test:

install: GCP_Bucket/main.tf GCP_Bucket/model.yaml
	kubectl apply -f GCP_Bucket/model.yaml

clean: 
	- kubectl delete -f GCP_Bucket/model.yaml

.PHONY: all