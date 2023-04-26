###########################################################
# Makefile
# 
#  Organise build and dependancy
###########################################################
DOCKERFILE_OPERATOR= Docker/Dockerfile.operator
DOCKERFILE_WORKER= Docker/Dockerfile.worker
VERSION= latest
IMAGE_OPERATOR= gcr.io/universal-ion-377015/kappform-operator:$(VERSION)
IMAGE_WORKER= gcr.io/universal-ion-377015/kappform-worker:$(VERSION)
SUBDIRS := $(wildcard */.)

all: build test install

build: docker-images

docker-images: docker-image-operator docker-image-worker

docker-image-operator: $(DOCKERFILE_OPERATOR)
	docker build -f $(DOCKERFILE_OPERATOR) . -t $(IMAGE_OPERATOR)
docker-image-worker: ${DOCKERFILE_WORKER}
	docker build -f $(DOCKERFILE_WORKER) . -t $(IMAGE_WORKER)

auth:
	- kubectl delete secret kappform-key
	kubectl create secret generic kappform-key --from-file=key.json=auth.json
	
test:

install: auth
	docker push $(IMAGE_OPERATOR)
	docker push $(IMAGE_WORKER)
	GOOGLE_PROJECT=$(shell gcloud config get-value project) envsubst < src/operator/deployment.yaml | kubectl apply -f -
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