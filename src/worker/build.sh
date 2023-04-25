#!/bin/sh

set -x
ACTION=$1
[ "x$ACTION" == "x" ] && echo "Usage /build.sh <plan|apply>" && exit 255
[ "x$GIT" == "x" ] && echo "ERROR GIT environnement variable must be defined" && exit 255
set -e

git clone $GIT /workdir
cd /workdir
echo "##################################################################"
find .
export 
echo "##################################################################"
[ "x$PREFIX" != "x" ] && cd $PREFIX
/usr/bin/terraform init -upgrade

case "$ACTION" in
    plan)
        /usr/bin/terraform plan
    ;;
    apply)
        /usr/bin/terraform apply -auto-approve
    ;;
    fmt)
        /usr/bin/terraform fmt
    ;;
esac