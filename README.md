# Kappform

Your own Infrastructure selfservice for Devops !

## Architecture

![General kappform architecture.](https://raw.githubusercontent.com/matgou/kappform/main/docs/kappform_architecture_v2023-03-31.png)

## Installation

To install the operator to your cluster just run the following command :

```bash
   make && make install
```

## Runing unittest

Unitstest are build for minikube in a local environment :

```bash
   minikube start
   make test
```

## Remove operator from your cluster

```bash
  make clean
```

## Other solutions
* kratix (https://github.com/syntasso/kratix)

