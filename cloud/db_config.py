import os


def _bool_env(key, default=False):
    return os.environ.get(key, str(default)).lower() in ('1', 'true', 'yes', 'on')


class DBConfig:
    """Central DB configuration. Select environment via DATAFUSION_ENV env var.

    Usage:
        DATAFUSION_ENV=local  python etl_pipeline.py
        DATAFUSION_ENV=cloud  python etl_pipeline.py
    """

    # Local MySQL (default)
    LOCAL = {
        'host': os.environ.get('DATAFUSION_LOCAL_HOST', 'localhost'),
        'port': int(os.environ.get('DATAFUSION_LOCAL_PORT', '3306')),
        'user': os.environ.get('DATAFUSION_LOCAL_USER', 'datafusion'),
        'password': os.environ.get('DATAFUSION_LOCAL_PASSWORD', 'datafusion123'),
    }

    # Cloud MySQL (set these env vars after provisioning)
    CLOUD = {
        'host': os.environ.get('DATAFUSION_CLOUD_HOST', ''),
        'port': int(os.environ.get('DATAFUSION_CLOUD_PORT', '3306')),
        'user': os.environ.get('DATAFUSION_CLOUD_USER', 'datafusion'),
        'password': os.environ.get('DATAFUSION_CLOUD_PASSWORD', ''),
    }

    def __init__(self, environment=None):
        self.environment = environment or os.environ.get('DATAFUSION_ENV', 'local')

    @property
    def _creds(self):
        return self.CLOUD if self.environment == 'cloud' else self.LOCAL

    @property
    def uri(self):
        c = self._creds
        return f"mysql+mysqlconnector://{c['user']}:{c['password']}@{c['host']}:{c['port']}"

    def oltp_uri(self):
        return f"{self.uri}/datafusion_oltp"

    def dw_uri(self):
        return f"{self.uri}/datafusion_dw"

    @property
    def is_cloud(self):
        return self.environment == 'cloud'