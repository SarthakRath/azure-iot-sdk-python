# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
import pytest
import asyncio
import functools
import e2e_settings
import logging
import stress_results
import time
import datetime
from utils import create_client_object
from service_helper import ServiceHelper
from azure.iot.device.iothub.aio import IoTHubDeviceClient, IoTHubModuleClient

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def brand_new_client(device_identity, client_kwargs, service_helper, device_id, module_id):
    service_helper.set_identity(device_id, module_id)

    # Keep this here.  It is useful to see this info inside the inside devops pipeline test failures.
    logger.info(
        "Connecting device_id={}, module_id={}, to hub={} at {} (UTC)".format(
            device_id, module_id, e2e_settings.IOTHUB_HOSTNAME, datetime.datetime.utcnow()
        )
    )

    client = create_client_object(
        device_identity, client_kwargs, IoTHubDeviceClient, IoTHubModuleClient
    )

    yield client

    logger.info("---------------------------------------")
    logger.info("test is complete.  Shutting down client")
    logger.info("---------------------------------------")

    await client.shutdown()


@pytest.fixture(scope="function")
async def client(brand_new_client):
    client = brand_new_client

    await client.connect()

    yield client


@pytest.fixture(scope="module")
async def service_helper(event_loop, executor):
    service_helper = ServiceHelper(event_loop, executor)
    await asyncio.sleep(3)
    yield service_helper
    logger.info("shutting down service_helper")
    await service_helper.shutdown()


@pytest.fixture(scope="function")
def stress_measurements(request):
    """
    Fixture to create an object to store our stress measurements.  This fixture also tracks
    the length of a test and stores the results into the pytest function object so we can
    log them at the end of the test (inside `pytest_sessionfinish`.
    """
    start_time = time.time()
    measurements = stress_results.Measurements()

    yield measurements

    measurements.total_elapsed_time = time.time() - start_time

    # Temporarily store results so we can print them at the end of the run.
    # Later, we will push these results to some analytics store.
    request.node.stress_measurements = measurements


@pytest.hookimpl
def pytest_sessionfinish(session, exitstatus):
    """
    Log stress results to stdout at the end of a test run.
    """
    for item in session.items:
        if getattr(item, "stress_measurements", None):
            it = item.get_closest_marker("it")
            if it:
                name = it.args[0]
            else:
                name = item.name
            stress_results.print_measurements(item.stress_measurements, name)
