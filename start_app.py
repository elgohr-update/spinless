import os
import threading
import time

from flask import Flask, request, jsonify, Response
import time
from logging.config import dictConfig

from flask import request, jsonify, Response, abort
from flask_api import FlaskAPI

from libs.job_api import *
from libs.vault_api import Vault

DEPLOY_ACTION = "deploy"
from libs.helm_api import Helm
from libs.task_logs import JobContext, tail_f
from services.kubernetes import deploy

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://sys.stdout',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
})

app = FlaskAPI(__name__)
app.config["VAULT_ADDR"] = os.getenv("VAULT_ADDR")
app.config["VAULT_ROLE"] = os.getenv("VAULT_ROLE")
app.config["VAULT_SECRETS_PATH"] = os.getenv("VAULT_SECRETS_PATH")


@app.route('/')
def main():
    return "Yes i am still here, thanks for asking."


@app.route('/jobs/create', methods=['POST'])
def create_job_api():
    data = request.get_json()
    if not data:
        return abort(Response("Give some payload"))
    app.logger.info("Request to Start Job is {}".format(data))
    action = data.get("action", None)
    if not action:
        return abort(Response("Provide 'action' field in payload"))

    app.logger.info("Requested to start job. Starting.")
    log_id = create_job(action)
    return {"log_id": log_id}


@app.route('/jobs/get/<job_id>', methods=['GET'])
def get_job_api(job_id):
    app.logger.info("Request to get_log  is {}".format(job_id))
    if not job_id:
        return abort(Response("No log id provided"))
    return Response(get_job_log(job_id), mimetype='text/plain')


@app.route('/jobs/status/<job_id>', methods=['GET'])
def job_status_api(job_id):
    app.logger.info("Request to get_log  is {}".format(job_id))
    if not job_id:
        return abort(Response("No job id provided"))
    return Response(get_job_status(job_id), mimetype='text/plain')


@app.route('/jobs/cancel/<job_id>', methods=['GET'])
def cancel_job_api(job_id):
    app.logger.info("Request to get_log is {}".format(job_id))
    if not job_id:
        return abort(Response("No job id provided"))
    if cancel_job(job_id):
        return Response("Stopped job {}".format(job_id))
    else:
        return abort(Response("Job {} was not running".format(job_id)))


@app.route('/kubernetes/deploy', methods=['POST'])
def pipelines():
    data = request.get_json()
    app.logger.info("Request to CICD is {}".format(data))

    action_type = data.get("action_type", None)
    if action_type:
        if action_type == "deploy":
            ctx = JobContext(deploy, app, data).start()

        elif action_type == 'cancel':
            JobContext.cancel(data.get("id"))
            return

    return jsonify({'id': str(ctx.id) })


@app.route('/status/<owner>/<repo>/<log_id>')
def log(owner, repo, log_id):
    file = '{}/{}/{}.log'.format(owner, repo, log_id)
    return Response(tail_f(file, 1.0), mimetype='text/plain')


@app.route('/namespaces', methods=['GET'])
def namespaces():
    data = request.get_json()
    app.logger.info("Request to list namespaces is {}".format(data))
    repo_name = data['repo_name']
    return jsonify({})


if __name__ == '__main__':
    app.run(host='0.0.0.0')
