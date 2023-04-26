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
echo 'terraform { 
    backend "s3" {  
     }
}' >> backend-$(shuf -i1-10000 -n1).tf
/usr/bin/terraform init -upgrade $BACKEND_CONFIG

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