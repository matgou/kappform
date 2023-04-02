###########################################################
# Makefile
# 
#  Organise build and dependancy
###########################################################
DOCKERFILE_OPERATOR= Docker/Dockerfile.operator
VERSION= main
IMAGE_OPERATOR= kappform-operator:$(VERSION)
SUBDIRS := $(wildcard */.)

all: build test install

build: docker-images

docker-images: $(DOCKERFILE_OPERATOR)
	docker build -f $(DOCKERFILE_OPERATOR) . -t $(IMAGE_OPERATOR)

test:

install:
	kubectl apply -f src/crd/crd-kappform-model.yaml

clean:
	$(MAKE) -C examples clean
	docker rmi $(IMAGE_OPERATOR)

demo:
	$(MAKE) -B -C examples

.PHONY: all