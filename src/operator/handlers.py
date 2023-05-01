#!/bin/env python
"""
Kybernetes Operator to manage model and plateform objects.
This operator run kubernetes-job to deploy terraform as service

USAGE : kopf run /src/handlers.py --verbose

See Docker/Dockerfile.orperator and src/operator/deployment.yaml for more information about usage 
"""

import os
import logging
import kubernetes
from kubernetes.client.exceptions import ApiException
import shortuuid
import kopf
import yaml
################################
# Main environnement parametrage
################################
#kubernetes.config.load_incluster_config()
kubernetes.config.load_config()
kube_client = kubernetes.client
api_crd = kube_client.CustomObjectsApi()
api_batch = kube_client.BatchV1Api()

CRD_GROUP = 'kappform.dev'
CRD_VERSION = 'v1'
GOOGLE_PROJECT = os.getenv('GOOGLE_PROJECT') # Google project to pass to terraform job
IMAGE_WORKER = os.getenv('IMAGE_WORKER', 'kappform-worker:latest')     # Static Image to start job
TFSTATE_BUCKET = os.getenv('TFSTATE_BUCKET', 'tfstate-7e0a831c905c2b9e3f82') # Bucket pour le stockage du tfstate
KUBE_PROVIDER = os.getenv('KUBE_PROVIDER', 'minikube')   # Provider kubernetes GKE ou EKS
TFSTATE_REGION = os.getenv('TFSTATE_REGION', 'eu-west-3') # Region pour le backend

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
    job_name = f'apply-{namespace}-{name}-{uuid}'
    model_spec=spec.get('model_spec', {})
    git = model_spec.get('git', None)
    prefix = model_spec.get('prefix', '.')
    BACKEND_CONFIG=f"-backend-config=bucket={TFSTATE_BUCKET} -backend-config=key={kind}.{name}.{namespace} -backend-config=region={TFSTATE_REGION}"
    if git is None:
        logger.error("Error model_spec doesn't containt git field : %s", model_spec)
        return 1
    metadata = kube_client.V1ObjectMeta(
        name=job_name,
        labels={
            "job_name": job_name,
            f"{CRD_GROUP}/application": "kappform-job",
            f"{CRD_GROUP}/kind-ref": f"{kind}",
            f"{CRD_GROUP}/{kind}-ref": f"{name}.{namespace}", 
            }
        )
    
    container = kube_client.V1Container(
        image=IMAGE_WORKER,
        name=name,
        image_pull_policy="IfNotPresent",
        args=[mode],
        env=[
            kube_client.V1EnvVar(name="GOOGLE_APPLICATION_CREDENTIALS", value="/var/secrets/google/key.json"),
            kube_client.V1EnvVar(name="AWS_SHARED_CREDENTIALS_FILE", value="/var/secrets/aws/credentials"),
            kube_client.V1EnvVar(name="GOOGLE_PROJECT", value=GOOGLE_PROJECT),
            kube_client.V1EnvVar(name="GIT", value=git),
            kube_client.V1EnvVar(name="PREFIX", value=prefix),
            kube_client.V1EnvVar(name="BACKEND_CONFIG", value=BACKEND_CONFIG),
        ],
        volume_mounts=[
            kube_client.V1VolumeMount(name="google-cloud-key", mount_path="/var/secrets/google"),
            kube_client.V1VolumeMount(name="aws-cloud-key", mount_path="/var/secrets/aws"),
        ],
    )
    pod_template = kube_client.V1PodTemplateSpec(
            spec=kube_client.V1PodSpec(restart_policy="Never", containers=[container], volumes=[
                kube_client.V1Volume(name="google-cloud-key", secret=kube_client.V1SecretVolumeSource(secret_name="google-cloud-key")),
                kube_client.V1Volume(name="aws-cloud-key", secret=kube_client.V1SecretVolumeSource(secret_name="aws-cloud-key")),
            ]),
            metadata=kube_client.V1ObjectMeta(name="tf-action", labels={"pod_name": "tf-action"}),

        )
    job = kube_client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=metadata,
        spec=kube_client.V1JobSpec(backoff_limit=backoff_limit, template=pod_template)
    )
    try:
        api_batch.create_namespaced_job(namespace=namespace, body=job)
    except ApiException as api_exception:
        logging.error("Exception when calling BatchV1Api->create_namespaced_cron_job: %s", api_exception)
        logging.exception(api_exception)
        logging.error("job %s", yaml.dump(job.to_dict()))
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
        model_status={'prj-status': 'Registering-Creating-Job'}
        logging.info("Setting status to: %s", model_status)
    else:
        model_status={'prj-status': 'Error-invalid-spec'}
        logging.error("Setting status to: %s", model_status)
    return model_status


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


