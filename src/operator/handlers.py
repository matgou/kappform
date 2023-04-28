#!/bin/env python
"""
Kybernetes Operator to manage model and plateform objects.
This operator run kubernetes-job to deploy terraform as service

USAGE : kopf run /src/handlers.py --verbose

See Docker/Dockerfile.orperator and src/operator/deployment.yaml for more information about usage 
"""

import os
import logging
import yaml
import pykube
import kubernetes
from kubernetes.client.exceptions import ApiException
import shortuuid
import kopf
################################
# Main environnement parametrage
################################
kubernetes.config.load_incluster_config()
api_crd = kubernetes.client.CustomObjectsApi()
api_kube = pykube.HTTPClient(pykube.KubeConfig.from_service_account())

CRD_GROUP = 'kappform.dev'
CRD_VERSION = 'v1'
GOOGLE_PROJECT = os.getenv('GOOGLE_PROJECT') # Google project to pass to terraform job
IMAGE_WORKER = os.getenv('IMAGE_WORKER')     # Static Image to start job
TFSTATE_BUCKET = os.getenv('TFSTATE_BUCKET') # Bucket pour le stockage du tfstate
KUBE_PROVIDER = os.getenv('KUBE_PROVIDER')   # Provider kubernetes GKE ou EKS
TFSTATE_REGION = os.getenv('TFSTATE_REGION') # Region pour le backend

################################
# Utils functions
################################
async def find_one(kind, namespace, name):
    """
    Return an object definition by getting int on kubernetes

    Keyword arguments:
    kind -- the CRD name of object (type of crd)
    namespace -- the namespace of the object to update
    name -- the name of the object to update
    """
    plural = f'{kind}s'
    prj = api_crd.get_namespaced_custom_object(CRD_GROUP, CRD_VERSION, namespace, plural, name)
    return prj

async def update_one(kind, namespace, name, obj):
    """
    Return an object definition by getting int on kubernetes

    Keyword arguments:
    kind -- the CRD name of object (type of crd)
    namespace -- the namespace of the object to update
    name -- the name of the object to update
    """
    plural = f'{kind}s'
    api_crd.patch_namespaced_custom_object(CRD_GROUP, CRD_VERSION, namespace, plural, name, obj)
    logging.info("finished update %s : %s.%s", kind, name, namespace)

async def update_object(kind, namespace, name, new_status):
    """
    Update status of an crd object to report

    Keyword arguments:
    kind -- the CRD name of object (type of crd)
    namespace -- the namespace of the object to update
    name -- the name of the object to update
    new_status -- the new status of the object
    """
    logging.info("start update %s's status: %s.%s to %s", kind, name, namespace, new_status)
    try:
        # Find the object on kubernetes
        prj = await find_one(kind, namespace, name)
        logging.debug("%s", prj)
        prj['status'][f'create_{kind}_handler'] = {'prj-status': new_status}
        # Patch the object
        await update_one(kind, namespace, name, prj)
    except ApiException as excep:
        logging.error("Error when updating prj : %s", str(excep))

async def start_terraformjob(spec, name, namespace, logger, mode, kind, backoff_limit=0):
    """
    Start a kubernetes job to execute terraform in a pod
    """
    uuid=shortuuid.uuid().lower()
    logging.info("processing: %s", spec)
    model_spec=spec.get('model_spec', {})
    git = model_spec.get('git', None)
    prefix = model_spec.get('prefix', '.')
    if git is None:
        logger.error("Error model_spec doesn't containt git field : %s", model_spec)
        return 1

    pod_data = yaml.safe_load(f"""
        apiVersion: batch/v1
        kind: Job
        backoffLimit: {backoff_limit}
        metadata:
            labels:
                {CRD_GROUP}/application: kappform-job
                {CRD_GROUP}/kind-ref: {kind}
                {CRD_GROUP}/{kind}-ref: {name}.{namespace} 
            name: apply-{namespace}-{name}-{uuid}
        spec:
            ttlSecondsAfterFinished: 900
            backoffLimit: 0
            template:
                spec:
                    volumes:
                    - name: google-cloud-key
                      secret:
                        secretName: google-cloud-key
                    - name: aws-cloud-key
                      secret:
                        secretName: aws-cloud-key
                    restartPolicy: Never
                    containers:
                    - name: tf-action
                      volumeMounts:
                      - name: google-cloud-key
                        mountPath: /var/secrets/google
                      - name: aws-cloud-key
                        mountPath: /var/secrets/aws
                      image: "{IMAGE_WORKER}"
                      args:
                      - {mode}
                      env:
                      - name: GOOGLE_APPLICATION_CREDENTIALS
                        value: /var/secrets/google/key.json
                      - name: AWS_SHARED_CREDENTIALS_FILE
                        value: /var/secrets/aws/credentials
                      - name: GOOGLE_PROJECT
                        value: {GOOGLE_PROJECT}
                      - name: GIT
                        value: "{git}"
                      - name: PREFIX
                        value: "{prefix}"
                      - name: BACKEND_CONFIG
                        value : "-backend-config=bucket={TFSTATE_BUCKET} -backend-config=key={kind}.{name}.{namespace} -backend-config=region={TFSTATE_REGION}"
    """)
    kopf.adopt(pod_data)

    try:
        job = pykube.Job(api_kube, pod_data)
        job.create()
    except Exception as e:
        logging.error(f"Error when creating job", e)
        return -1
    return 1


@kopf.on.delete('models')
async def delete_model_handler(spec, **_):
    """ TODO 
    Handle deletion of a models, do not delete model if plateform match
    """
    logging.info("A handler delete_model_handler is called with body: %s", spec)
    pass


@kopf.on.create('models')
async def create_model_handler(body, spec, name, namespace, logger, **_):
    """ 
    Handle creation of a models, do not delete model if plateform match
    """
    logging.info("A handler create_model_handler is called with body: %s", spec)
    kopf.info(body, reason='Creating', message='Start model initialisation {namespace}/{name}')
    rc=await start_terraformjob({'model_spec': spec}, name, namespace, logger, 'fmt', 'model')
    if rc > 0:
        return {'prj-status': 'Registering-Creating-Job'}
    else:
        return {'prj-status': 'Error-invalid-spec'}



@kopf.on.create('platforms')
async def create_platform_handler(body, spec, name, namespace, logger, **_):
    logging.info("A handler create_platform_handler is called with body: %s", spec)
    # Check if model exist
    model = await find_one('model', namespace, spec['model'])
    if model['status']['create_model_handler']['prj-status'] != "Ready":
        return {'prj-status': 'Bad-model-state'}
    new_spec = {'plateform_spec': spec, 'model_spec': model['spec']}

    kopf.info(body, reason='Creating', message='Start platform initialisation {namespace}/{name}')
    rc=await start_terraformjob(new_spec, name, namespace, logger, 'apply', 'platform')
    if rc > 0:
        return {'prj-status': 'Registering-Creating-Job'}
    else:
        return {'prj-status': 'Error-invalid-spec'}


@kopf.on.field('job', field='status')
async def job_change(body, namespace, logger, new, **_):
    """
    When job change status, update model status
    """
    active = new.get('active', None)
    succeeded = new.get('succeeded', None)
    labels = body['metadata']['labels']
    logging.info("active: %s", active)
    logging.info("succeeded: %s", succeeded)
    logging.info("labels: %s", labels)
    # Extract kappform labels
    if labels:
        kind = labels.get(f'{CRD_GROUP}/kind-ref', None)
        if kind is None:
            logger.info(f'{CRD_GROUP}/kind-ref not found')
            return
        ref = labels.get(f'{CRD_GROUP}/{kind}-ref', None)
        if ref is None:
            logger.info(f'{CRD_GROUP}/{kind}-ref not found')
            return
        else:
            [obj, namespace] = ref.split('.')
            if obj:
                status='Error-see-logs'
                if active:
                    status='Registering'
                elif succeeded:
                    status='Ready'
                # Update source CRD object status
                logger.info(f'setting {kind}/{obj}.{namespace} to {status}')
                await update_object(kind, namespace, obj, status)
    return


