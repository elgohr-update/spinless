import hvac
import os

dev_mode = os.getenv("dev_mode", False)

dev_settings = {
    "vault_addr": "localhost",
    "vault_role": "developer",
    "vault_secr_path": "secretv2/test",
    "vault_token": "s.AUazaAyTHxBzguX6vJRwN15j"
}

class Vault:
    def __init__(self, logger,
                 vault_server,
                 service_role,
                 root_path=None,
                 owner=None,
                 repo=None,
                 version=None,
                 vault_secrets_path=None):
        self.root_path = root_path
        self.owner = owner
        self.repo = repo
        self.version = version
        self.app_path = "{}-{}-{}".format(owner, repo, version)

        if dev_mode:
            self.vault_server = dev_settings["vault_addr"],
            self.service_role = dev_settings["vault_role"],
            self.vault_secrets_path = dev_settings["vault_secr_path"]
        else:
            self.vault_server = vault_server
            self.service_role = service_role
            self.vault_secrets_path = vault_secrets_path

        self.logger = logger
        self.client = hvac.Client(url=vault_server)
        self.dev_mode = dev_mode

    def auth_client(self):
        if not self.dev_mode:
            f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
            jwt = f.read()
            self.client.auth_kubernetes(self.service_role, jwt)
        else:
            self.client.lookup_token(dev_settings["vault_token"])
        return self.client

    def get_self_app_env(self):
        client = self.auth_client()
        try:
            self.logger.info("Vault secrets path is: {}".format(self.vault_secrets_path))
            env = client.read(self.vault_secrets_path)
            if not env or not env['data']:
                self.logger.error("Data not found for secret path {}".format(self.vault_secrets_path))
                return {}
            return env
        except Exception as e:
            self.logger.info("Vault get_self_app_env exception is: {}".format(e))
            return {}

    def get_env(self, env_or_app):
        client = self.auth_client()
        path = "{}/{}/{}/{}/{}".format(
                self.root_path, self.owner, self.repo, self.version, env_or_app)
        self.logger.info("Get_env in vault path is: {}".format(path))
        try:
            env = client.read(path)
            self.logger.info("ENV from vault is {}: ".format(env))
            return env['data']
        except Exception as e:
            self.logger.info("Vault get_env exception is: {}".format(e))
            return {}

    def create_policy(self):
        client = self.auth_client()
        policy_name = "{}-{}-policy".format(self.owner, self.repo)
        policy_path = "{}/{}/{}/*".format(self.root_path, self.owner, self.repo)
        self.logger.info("Policy name is: {}".format(policy_name))
        self.logger.info("Policy path is: {}".format(policy_path))
        policy_1_path = 'path "{}" '.format(policy_path)
        policy_2_path = '{ capabilities = ["create", "read", "update", "delete", "list"]}'
        try:
            client.set_policy(policy_name, policy_1_path+policy_2_path)
        except Exception as e:
            self.logger.info("Vault create_policy exception is: {}".format(e))
        return policy_name

    def create_role(self):
        self.logger.info("Creating service role")
        client = self.auth_client()
        policy_name = self.create_policy()
        try:
            client.create_role("{}-role".format(self.app_path),
                               mount_point="kubernetes",
                               bound_service_account_names="{}".format(self.app_path),
                               bound_service_account_namespaces="*",
                               policies=[policy_name], ttl="1h")
        except Exception as e:
            self.logger.info("Vault create_role exception is: {}".format(e))
        return

