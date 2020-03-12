import subprocess
import uuid
import time
import requests
import urllib.parse
from http.cookiejar import CookieJar
from jinja2 import Environment, FileSystemLoader
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPHandler


class SpinnakerPipeline:
    def __init__(self, data, logger, spinnaker_api, spinnaker_auth_token):
        self.logger = logger
        self.logger.info("SpinnakerPipeline init")
        self.data = data
        self.spinnaker_api = spinnaker_api
        self.spinnaker_auth_token = spinnaker_auth_token

    def auth_cookie(self):
        cj = CookieJar()
        request = Request(url=urllib.parse.urljoin(self.spinnaker_api, "login"),
                          headers={'Authorization': 'Bearer {}'.format(
                              self.spinnaker_auth_token)})
        opener = build_opener(HTTPCookieProcessor(cj), HTTPHandler())
        go = opener.open(request)
        for cookie in cj:
            if cookie.name == "SESSION":
                self.logger.info("Cookie is returned")
                return cookie.value
        return

    def application_create(self, application):
        with open("/opt/spinnaker/app.yaml", "w") as app_file:
            j2_env = Environment(loader=FileSystemLoader("/opt/spinnaker/templates/"))
            gen_template = j2_env.get_template(
                'app.j2').render(application_name=application)
            app_file.write(gen_template)
        proc = subprocess.Popen(["spin application save --file /opt/spinnaker/app.yaml"],
                                stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        self.logger.info("Creation of application output: {}".format(
            out.decode("utf-8") if out else None))
        self.logger.info("Creation of application error: {}".format(
            err.decode("utf-8") if err else None))
        return

    def create(self):
        self.logger.info("Request to pipeline_create is {}".format(self.data))
        owner = self.data["owner"]
        repo = self.data["repo"]
        application = "{}-{}".format(owner, repo)
        self.application_create(application)
        with open("/opt/spinnaker/deploy_pipeline.yaml", "w") as pipeline_file:
            j2_env = Environment(loader=FileSystemLoader("/opt/spinnaker/templates/"))
            gen_template = j2_env.get_template(
                'deploy_pipeline.j2').render(
                application=application,
                helm_package=application,
                repo_slug=repo,
                default_artifact_uuid=uuid.uuid1(),
                artifact_uuid=uuid.uuid1(),
                match_artifact_uuid=uuid.uuid1(),
                stages_default_artifact_uuid=uuid.uuid1(),
                stages_artifact_uuid=uuid.uuid1(),
                stages_match_artifact_uuid=uuid.uuid1())
            pipeline_file.write(gen_template)
        proc = subprocess.Popen(["spin pipeline save --file /opt/spinnaker/deploy_pipeline.yaml"],
                                stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        self.logger.info("Creation of deploy pipeline output: {}".format(
            out.decode("utf-8") if out else None))
        self.logger.info("Creation of deploy pipeline error: {}".format(
            err.decode("utf-8") if err else None))
        return

    def deploy(self):
        self.logger.info("Request to pipeline_deploy is {}".format(self.data))
        timestamp = str(round(time.time() * 100))
        application = "{}-{}".format(self.data["owner"], self.data["repo"])
        data = {"namespace": "{}".format(self.data['namespace'])}
        cookies = {"SESSION": self.auth_cookie()}
        headers = {'Content-Type': 'application/json'}
        url = urllib.parse.urljoin(
                self.spinnaker_api, "{}/deploy".format(application))
        self.logger.info("URL for deploy: {}".format(url))
        response = requests.post(
            url=url,
            headers=headers,
            cookies=cookies,
            json=data
        )
        self.logger.info("Request to deploy status_code: {}".format(response.status_code))
        pipeline_id = response.json()["ref"].split("/")[-1]
        return {"pipeline_id": pipeline_id}

    def cancel(self):
        # app.logger.info("Request to pipeline_cancel {}".format(self.data))
        application = "{}-{}".format(self.data["owner"], self.data["repo"])
        pipeline_id = self.data['id']
        return {}