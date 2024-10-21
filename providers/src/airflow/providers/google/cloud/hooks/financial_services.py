# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

from google.cloud import secretmanager
from googleapiclient.discovery import Resource, build

from airflow.models import Variable
from airflow.providers.google.common.hooks.base_google import GoogleBaseHook


class FinancialServicesHook(GoogleBaseHook):
    """
    Hook for interacting with the Google Financial Services API.

    Args:
        location (str | None, optional): Location of the Google Cloud Platform
            project. Defaults to None.
        gcp_conn_id (str, optional): Identifier of connection to Google Cloud Platform.
            Defaults to "google_cloud_default".
        api_version (str, optional): API version for the Financial Services API.
            Defaults to "v1".
        dev_key_var (str, optional): Airflow variable name for accessing/saving the
            developer key. If key is not provided, secret value will be stored in a
            variable with the default name. Defaults to "AMLAI_API_KEY".
        dev_key_secret_uri (str | None, optional): URI for the GCP secret (Secrets
            Manager) containing the developer key. Secret will only be accessed if
            dev_key_var does not exist. Defaults to None.
    """

    connection: build | None = None

    def __init__(
        self,
        location: str | None = None,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1",
        dev_key_var: str = "AMLAI_API_KEY",
        dev_key_secret_uri: str | None = None,
        **kwargs,
    ) -> None:
        if kwargs.get("delegate_to") is not None:
            raise RuntimeError(
                "The `delegate_to` parameter has been deprecated before and finally"
                " removed in this version"
                " of Google Provider. You MUST convert it to `impersonate_chain`"
            )
        super().__init__(
            gcp_conn_id=gcp_conn_id,
            impersonation_chain=None,
        )
        self.dev_key_var = dev_key_var
        self.dev_key_secret_uri = dev_key_secret_uri
        self.api_version = api_version
        self.location = location

    def get_developer_key(self):
        if Variable.get(key=self.dev_key_var, default_var=None):
            developer_key = Variable.get(key=self.dev_key_var)
        elif self.dev_key_secret_uri:
            client = secretmanager.SecretManagerServiceClient()
            secret = client.access_secret_version(name=self.dev_key_secret_uri)
            developer_key = secret.payload.data.decode()
            Variable.set(key=self.dev_key_var, value=developer_key)
        else:
            raise ValueError("Either dev_key_var or dev_key_secret_uri must be provided")
        return developer_key

    def get_conn(self) -> Resource:
        """
        Establish a connection to the Google Financial Services API.

        :return: a Google Cloud Financial Services service object.
        """
        if not self.connection:
            # TODO changes when allow listed
            self.connection = build(
                serviceName="financialservices",
                version=self.api_version,
                http=None,
                cache_discovery=False,
                discoveryServiceUrl="https://financialservices.googleapis.com/$discovery/rest?version=v1",
                developerKey=self.get_developer_key(),
                credentials=self.get_credentials(),
            )

        return self.connection

    def get_instance(self, instance_resource_uri: str) -> dict:
        """
        Get an AML AI instance.

        Args:
            instance_id (str): The instance identifier
            project_id (str): Google Cloud Platform project_id containing the AML AI
                instance resource

        Returns:
            dict: A dictionary containing the instance metadata
        """
        conn = self.get_conn()
        response = conn.projects().locations().instances().get(name=instance_resource_uri).execute()
        return response

    def create_instance(self, instance_id: str, kms_key: str, location_resource_uri: str) -> dict:
        """
        Create an AML AI instance.

        Args:
            instance_id (str): The ID of the instance
            kms_key (str): The KMS key name used for CMEK (encryption-at-rest)
            project_id (str): Google Cloud Platform project_id containing the AML AI
                instance resource

        Returns:
            dict: A dictionary containing metadata for the create instance
                operation
        """
        conn = self.get_conn()
        response = (
            conn.projects()
            .locations()
            .instances()
            .create(
                parent=location_resource_uri,
                instanceId=instance_id,
                body={"kmsKey": kms_key},
            )
            .execute()
        )
        return response

    def delete_instance(self, instance_resource_uri: str) -> dict:
        """
        Delete an AML AI instance.

        Args:
            instance_resource_uri (str): The ID of the instance

        Returns:
            dict: A dictionary containing metadata for the delete instance
                operation
        """
        conn = self.get_conn()
        response = conn.projects().locations().instances().delete(name=instance_resource_uri).execute()
        return response
