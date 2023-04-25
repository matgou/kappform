import kopf
import logging
import pykube
import kubernetes
from kubernetes.client.exceptions import ApiException
import shortuuid
import yaml
import asyncio

kubernetes.config.load_incluster_config()
api = kubernetes.client.CustomObjectsApi()

CRD_GROUP = 'kappform.dev'
CRD_VERSION = 'v1'
GOOGLE_PROJECT = 'universal-ion-377015'

async def update_object(kind, namespace, name, status):
    """
    Update status of model
    """
    plural = f'{kind}s'
    logging.info("update %s/%s.%s to %s", plural, name, namespace, status)
    try:
        prj = api.get_namespaced_custom_object(CRD_GROUP, CRD_VERSION, namespace, plural, name)
        logging.info("%s", prj)
        prj['status'][f'create_{kind}_handler'] = {'prj-status': status}
        api.patch_namespaced_custom_object(CRD_GROUP, CRD_VERSION, namespace, plural, name,prj)
        logging.info("%s: %s", kind, prj)
    except ApiException as excep:
        logging.error("Error when updating prj : %s", str(excep))

async def start_terraformjob(body, spec, name, namespace, logger, mode, kind, backoffLimit=0):
    uuid=shortuuid.uuid().lower()
    logging.info(f"processing: {spec}")
    try:
        model_spec=spec['model_spec']
        git = model_spec['git']
        prefix = "."
        if 'prefix' in model_spec:
            prefix = model_spec['prefix']
    except Exception as e:
        kopf.PermanentError(str(e))
        logging.error(f"Error when creating job", e)
        return 1

    pod_data = yaml.safe_load(f"""
        apiVersion: batch/v1
        kind: Job
        backoffLimit: {backoffLimit}
        metadata:
            labels:
                {CRD_GROUP}/application: kappform-job
                {CRD_GROUP}/kind-ref: {kind}
                {CRD_GROUP}/{kind}-ref: {name}.{namespace} 
            name: apply-{namespace}-{name}-{uuid}
        spec:
            backoffLimit: 1
            template:
                spec:
                    volumes:
                    - name: google-cloud-key
                      secret:
                        secretName: kappform-key
                    restartPolicy: Never
                    containers:
                    - name: tf-action
                      volumeMounts:
                      - name: google-cloud-key
                        mountPath: /var/secrets/google
                      image: "gcr.io/universal-ion-377015/kappform-worker:latest"
                      args:
                      - {mode}
                      env:
                      - name: GOOGLE_APPLICATION_CREDENTIALS
                        value: /var/secrets/google/key.json
                      - name: GOOGLE_PROJECT
                        value: {GOOGLE_PROJECT}
                      - name: GIT
                        value: "{git}"
                      - name: PREFIX
                        value: "{prefix}"
    """)
    kopf.adopt(pod_data)

    try:
        api = pykube.HTTPClient(pykube.KubeConfig.from_service_account())
        job = pykube.Job(api, pod_data)
        job.create()
        api.session.close()
    except Exception as e:
        kopf.PermanentError(str(e))
        logging.error(f"Error when creating job", e)
        return -1
    return 1


@kopf.on.delete('models')
async def delete_model_handler(spec, **_):
    pass


@kopf.on.create('models')
async def create_model_handler(body, spec, name, namespace, logger, **kwargs):
    logging.info(f"A handler create_model_handler is called with body: {spec}")
    kopf.info(body, reason='Creating', message='Start model initialisation {namespace}/{name}')
    rc=await start_terraformjob(body, {'model_spec': spec}, name, namespace, logger, 'fmt', 'model')
    if rc > 0:
        return {'prj-status': 'Registering-Creating-Job'}
    else:
        return {'prj-status': 'Error-invalid-spec'}


async def find_model(name, namespace):
    plural = 'models'
    prj = api.get_namespaced_custom_object(CRD_GROUP, CRD_VERSION, namespace, plural, name)
    return prj

@kopf.on.create('platforms')
async def create_platform_handler(body, spec, name, namespace, logger, **kwargs):
    logging.info(f"A handler create_platform_handler is called with body: {spec}")
    # Check if model exist
    model = await find_model(spec['model'], namespace)
    if model['status']['create_model_handler']['prj-status'] != "Ready":
        return {'prj-status': 'Bad-model-state'}
    new_spec = {'plateform_spec': spec, 'model_spec': model['spec']}

    kopf.info(body, reason='Creating', message='Start platform initialisation {namespace}/{name}')
    rc=await start_terraformjob(body, new_spec, name, namespace, logger, 'apply', 'platform')
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


