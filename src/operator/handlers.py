import kopf
import logging
import pykube
import kubernetes
import shortuuid
import yaml
import asyncio

kubernetes.config.load_incluster_config()
api = kubernetes.client.CustomObjectsApi()

def update_model(namespace, name, status):
    """
    Update status of model
    """
    logging.info(f"update {namespace}/{name} state '{status}'")
    try:
        group = 'kappform.dev' # str | the custom resource's group
        version = 'v1' # str | the custom resource's version
        plural = 'models'
        prj = api.get_namespaced_custom_object(group, version, namespace, plural, name)
        prj['status']['create_model_handler'] = {'prj-status': status}
        api.patch_namespaced_custom_object(group, version, namespace, plural, name,prj)
        logging.info(f"models: '{prj}'")
    except Exception as e:
        logging.error(f"Error when updating prj", e)

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
                application: kappform-engine
                {kind}-ref: {name}.{namespace} 
            name: apply-{namespace}-{name}-{uuid}
        spec:
            backoffLimit: 1
            template:
                spec:
                    restartPolicy: Never
                    containers:
                    - name: tf-action
                      image: "gcr.io/universal-ion-377015/kappform-worker:latest"
                      args:
                      - {mode}
                      env:
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
    group = 'kappform.dev' # str | the custom resource's group
    version = 'v1' # str | the custom resource's version
    plural = 'models'
    prj = api.get_namespaced_custom_object(group, version, namespace, plural, name)
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
def job_change(body, spec, name, namespace, logger, old, new, **_):
    """
    When job change status, update model status
    """ 
    active = new.get('active', None)
    succeeded = new.get('succeeded', None)
    labels = body['metadata']['labels']
    logging.info(f"active: {active}")
    logging.info(f"succeeded: {succeeded}")
    logging.info(f"labels: {labels}")
    if labels:   
        model_ref = labels.get('model-ref', None)
        [model, namespace] = model_ref.split('.')
        if model:
            if active:
                update_model(namespace, model, 'Registering')
            else:
                if succeeded:
                    update_model(namespace, model, 'Ready')
                else:
                    update_model(namespace, model, 'Error-see-logs')

    pass


