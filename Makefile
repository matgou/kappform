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
AWS_REGION= eu-west-3

###########################################################
# PARAM
###########################################################
# KUBE_PROVIDER=$(GOOGLE_PROVIDER)
KUBE_PROVIDER=$(AWS_PROVIDER)
AWS_REGION= eu-west-3
TFSTATE_BUCKET=tfstate-7e0a831c905c2b9e3f82
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



SUBDIRS := $(wildcard */.)

all: login build test install

build: docker-images

login:
ifeq ($(KUBE_PROVIDER),$(AWS_PROVIDER))
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com
endif

docker-images: docker-image-operator docker-image-worker

docker-image-operator: $(DOCKERFILE_OPERATOR)
	docker build -f $(DOCKERFILE_OPERATOR) . -t $(IMAGE_OPERATOR)
docker-image-worker: ${DOCKERFILE_WORKER}
	docker build -f $(DOCKERFILE_WORKER) . -t $(IMAGE_WORKER)

auth:
ifeq ($(KUBE_PROVIDER),$(GOOGLE_PROVIDER))
	- kubectl delete secret kappform-key
	kubectl create secret generic kappform-key --from-file=key.json=auth.json
endif
	
test:

install: auth
	docker push $(IMAGE_OPERATOR)
	docker push $(IMAGE_WORKER)
	TFSTATE_BUCKET=$(TFSTATE_BUCKET) KUBE_PROVIDER=$(KUBE_PROVIDER) IMAGE_WORKER=$(IMAGE_WORKER) IMAGE_OPERATOR=$(IMAGE_OPERATOR) GOOGLE_PROJECT=$(shell gcloud config get-value project) envsubst < src/operator/deployment.yaml | kubectl apply -f -
	envsubst < src/crd/crd-kappform-model.yaml | kubectl apply -f -
	envsubst < src/crd/crd-kappform-platform.yaml | kubectl apply -f -

clean:
	- kubectl delete -f src/operator/deployment.yaml
	- kubectl patch crd platforms.kappform.dev -p '{"metadata":{"finalizers":[]}}' --type=merge
	- kubectl patch crd models.kappform.dev -p '{"metadata":{"finalizers":[]}}' --type=merge
	- kubectl delete -f src/crd/crd-kappform-platform.yaml
	- kubectl delete -f src/crd/crd-kappform-model.yaml
	- docker rmi $(IMAGE_OPERATOR)

demo:
	$(MAKE) -B -C examples

.PHONY: all