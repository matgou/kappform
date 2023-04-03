import kopf
import logging
import pykube
import yaml
import asyncio

def update_model(namespace, name, status):
    """
    Update status of model
    """
    logging.info(f"update {namespace}/{name} state '{status}'")
    try:
        api = pykube.HTTPClient(pykube.KubeConfig.from_service_account())
        prj = pykube.object_factory(api, "kappform.dev/v1", "Models").objects(api).filter(namespace=namespace).get(name=name)
        logging.info(f"models: '{prj.obj}'")
        prj.obj['status']['create_prj_handler']['prj-status'] = status
        prj.update()
        api.session.close()
    except Exception as e:
        logging.error(f"Error when updating prj", e)

def start_terraformjob(body, spec, name, namespace, logger, mode):
    pod_data = yaml.safe_load(f"""
        apiVersion: batch/v1
        kind: Job
        backoffLimit: 1
        metadata:
            labels:
                application: kappform-engine
                model-ref: {name}.{namespace} 
            name: apply-{namespace}-{name}
        spec:
            template:
                spec:
                    containers:
                    - name: tf-action
                      image: busybox
                      command: ["sh", "-x", "-c", "echo {mode}"]
                    restartPolicy: Never
    """)
    kopf.adopt(pod_data)

    try:
        api = pykube.HTTPClient(pykube.KubeConfig.from_service_account())
        job = pykube.Job(api, pod_data)
        job.create()
        api.session.close()
    except Exception as e:
        logging.error(f"Error when creating job", e)


@kopf.on.delete('models')
async def delete_prj_handler(spec, **_):
    pass


@kopf.on.create('models')
async def create_prj_handler(body, spec, name, namespace, logger, **kwargs):
    logging.info(f"A handler create_prj_fn is called with body: {spec}")
    kopf.info(body, reason='Creating', message='Start model initialisation {namespace}/{name}')
    start_terraformjob(body, spec, name, namespace, logger, 'apply')
    return {'prj-status': 'creatingjob'}


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
                update_model(namespace, model, 'running')
            else:
                if succeeded:
                    update_model(namespace, model, 'succeeded')
                else:
                    update_model(namespace, model, 'failed')

    pass

