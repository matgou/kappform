###########################################################
# Makefile
# 
#  Organise build and dependancy
###########################################################
DOCKERFILE_OPERATOR= Docker/Dockerfile.operator
VERSION= latest
IMAGE_OPERATOR= gcr.io/universal-ion-377015/kappform-operator:$(VERSION)
SUBDIRS := $(wildcard */.)

all: build test install

build: docker-images

docker-images: $(DOCKERFILE_OPERATOR)
	docker build -f $(DOCKERFILE_OPERATOR) . -t $(IMAGE_OPERATOR)

test:

install:
	docker push $(IMAGE_OPERATOR)
	kubectl apply -f src/operator/deployment.yaml
	kubectl apply -f src/crd/crd-kappform-model.yaml

clean:
	- $(MAKE) -C examples clean
	- kubectl delete -f src/operator/deployment.yaml
	- kubectl delete -f src/crd/crd-kappform-model.yaml
	- docker rmi $(IMAGE_OPERATOR)

demo:
	$(MAKE) -B -C examples

.PHONY: all