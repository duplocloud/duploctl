import pytest 
import unittest

import time
import openapi_client
from pprint import pprint
from openapi_client.apis.tags import admin_api
from openapi_client.model.aws_account_security import AwsAccountSecurity
from openapi_client.model.aws_account_security_features import AwsAccountSecurityFeatures
from openapi_client.model.custom_data_ex import CustomDataEx
from openapi_client.model.password_policy import PasswordPolicy
from openapi_client.model.vpn_config import VpnConfig
import os

configuration = openapi_client.Configuration(
    host = os.getenv('DUPLO_HOST', None)
)
# add the bearer token to the configuration
token = os.getenv('DUPLO_TOKEN', None)

def test_using_oai():
  assert openapi_client.__version__ == "1.0.0"

  # Enter a context with an instance of the API client
  with openapi_client.ApiClient(
     configuration, 
     header_name="Authorization",
     header_value=f"Bearer {token}") as api_client:
    # Create an instance of the API class
    api_client.set_default_header("Content-Type", "application/json; charset=utf-8")
    api_instance = admin_api.AdminApi(api_client)
    try:
        api_response = api_instance.get_vpn_config()
        pprint(api_response)
    except openapi_client.ApiException as e:
        print("Exception when calling AdminApi->get_vpn_config: %s\n" % e)

def test_hello():
   assert 1 == 1
