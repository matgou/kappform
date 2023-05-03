###########################################################
# Makefile
# 
#  Organise build and dependancy
###########################################################
# CONST
###########################################################
DOCKERFILE_OPERATOR= Docker/Dockerfile.operator
DOCKERFILE_WORKER= Docker/Dockerfile.worker
VERSION= latest
GOOGLE_PROVIDER= GCP
AWS_PROVIDER= EKS
MINIKUBE_PROVIDER= MINIKUBE
AWS_REGION= eu-west-3

###########################################################
# PARAM
###########################################################
# KUBE_PROVIDER=$(GOOGLE_PROVIDER)
KUBE_PROVIDER=$(AWS_PROVIDER)
KUBE_PROVIDER=$(MINIKUBE_PROVIDER)
AWS_REGION= eu-west-3
TFSTATE_BUCKET=tfstate-7e0a831c905c2b9e3f82
TFSTATE_REGION=eu-west-3
###########################################################
ifeq ($(KUBE_PROVIDER),$(GOOGLE_PROVIDER))
GOOGLE_PROJECT=$(shell gcloud config get-value project)
IMAGE_OPERATOR= gcr.io/$(GOOGLE_PROJECT)/kappform-operator:$(VERSION)
IMAGE_WORKER= gcr.io/$(GOOGLE_PROJECT)/kappform-worker:$(VERSION)
endif
ifeq ($(KUBE_PROVIDER),$(AWS_PROVIDER))
AWS_ACCOUNT= $(shell aws sts get-caller-identity | jq -r .Account)
IMAGE_OPERATOR= $(AWS_ACCOUNT).dkr.ecr.eu-west-3.amazonaws.com/kappform-operator:$(VERSION)
IMAGE_WORKER= $(AWS_ACCOUNT).dkr.ecr.eu-west-3.amazonaws.com/kappform-worker:$(VERSION)
GOOGLE_PROJECT=$(shell gcloud config get-value project)
endif
ifeq ($(KUBE_PROVIDER),$(MINIKUBE_PROVIDER))
IMAGE_OPERATOR= kappform-operator:latest
IMAGE_WORKER= kappform-worker:latest
endif




SUBDIRS := $(wildcard */.)

all: login build push

build: docker-images

login:
ifeq ($(KUBE_PROVIDER),$(AWS_PROVIDER))
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com
endif

docker-images: docker-image-operator docker-image-worker

docker-image-operator: $(DOCKERFILE_OPERATOR)
ifeq ($(KUBE_PROVIDER),$(MINIKUBE_PROVIDER))
	@eval $$(minikube docker-env) ; \
	docker build -f $(DOCKERFILE_OPERATOR) . -t $(IMAGE_OPERATOR)
else
	docker build -f $(DOCKERFILE_OPERATOR) . -t $(IMAGE_OPERATOR)
endif

docker-image-worker: ${DOCKERFILE_WORKER}
ifeq ($(KUBE_PROVIDER),$(MINIKUBE_PROVIDER))
	@eval $$(minikube docker-env) ; \
	docker build -f $(DOCKERFILE_WORKER) . -t $(IMAGE_WORKER)
else
	docker build -f $(DOCKERFILE_WORKER) . -t $(IMAGE_WORKER)
endif

auth:
	touch auth.json
	- kubectl delete secret google-cloud-key
	kubectl create secret generic google-cloud-key --from-file=key.json=auth.json
	- kubectl delete secret aws-cloud-key
	touch auth_aws.txt
	kubectl create secret generic aws-cloud-key --from-file=credentials=auth_aws.txt
	
test:
	python src/operator/tests/handlers_test.py

push:
ifneq ($(KUBE_PROVIDER),$(MINIKUBE_PROVIDER))
	docker push $(IMAGE_OPERATOR)
	docker push $(IMAGE_WORKER)
endif

install: auth
	envsubst < src/crd/crd-kappform-model.yaml | kubectl apply -f -
	envsubst < src/crd/crd-kappform-platform.yaml | kubectl apply -f -
	TFSTATE_REGION=${TFSTATE_REGION} TFSTATE_BUCKET=$(TFSTATE_BUCKET) KUBE_PROVIDER=$(KUBE_PROVIDER) IMAGE_WORKER=$(IMAGE_WORKER) IMAGE_OPERATOR=$(IMAGE_OPERATOR) GOOGLE_PROJECT=$(shell gcloud config get-value project) envsubst < src/operator/deployment.yaml | kubectl apply -f -

clean: clean-demo
	- kubectl delete -f src/operator/deployment.yaml
	- kubectl patch crd platforms.kappform.dev -p '{"metadata":{"finalizers":[]}}' --type=merge
	- kubectl patch crd models.kappform.dev -p '{"metadata":{"finalizers":[]}}' --type=merge
	- kubectl delete -f src/crd/crd-kappform-platform.yaml
	- kubectl delete -f src/crd/crd-kappform-model.yaml
	- docker rmi $(IMAGE_OPERATOR)

demo:
	$(MAKE) -B -C examples

clean-demo:
	kubectl patch model google-storage-bucket  -p '{"metadata":{"finalizers":[]}}' --type=merge
	
.PHONY: all
