#!/bin/env python
"""
Test the kubernetes operator
"""
import unittest
import shlex
import subprocess
from kopf.testing import KopfRunner
import time
import os 
dir_path = os.path.dirname(os.path.realpath(__file__))
crd_yaml_path = f"{dir_path}/../../crd/crd-kappform-model.yaml"
object_yaml_path = f"{dir_path}/../../../examples/KUBE_Webserver/model.yaml"

class TestHandlersMethods(unittest.TestCase):
    """
    Test method for KOPF Handler
    """

    def test_create_model_handler(self):
        """
        This test will create a model CRD object and test the state of resulting job
        """
        with KopfRunner(['run', '-A', '--verbose', f'{dir_path}/../handlers.py']) as runner:
            subprocess.run(f"kubectl apply -f {crd_yaml_path}", shell=True, check=True)
            subprocess.run(f"kubectl apply -f {object_yaml_path}", shell=True, check=True)
            time.sleep(15)  # give it some time to react and to sleep and to retry

            subprocess.run(f"kubectl delete -f {object_yaml_path}", shell=True, check=True)
            time.sleep(1)  # give it some time to react
        print(runner.stdout)
        assert runner.exit_code == 0
        assert runner.exception is None
        assert 'Registering-Creating-Job' in runner.stdout
        
if __name__ == '__main__':
    unittest.main()