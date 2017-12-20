# -*- coding: utf-8 -*-

import time

from urllib.parse import urlencode

import aiohttp

from aiohttp.client_exceptions import ClientResponseError


JOB_INFO = 'job/{job_name}/api/json?depth={depth}'
JOB_NAME = 'job/{job_name}/api/json?tree=name'
BUILD_INFO = 'job/{job_name}/{number}/api/json?depth={depth}'

BUILD_JOB = 'job/{job_name}/build'
BUILD_WITH_PARAMS_JOB = 'job/{job_name}/buildWithParameters?{params}'


class JenkinsException(Exception):
    '''General exception type for jenkins-API-related failures.'''
    pass


class NotFoundException(JenkinsException):
    '''A special exception to call out the case of receiving a 404.'''
    pass


class JenkinsClient(object):
    def __init__(self, url, username=None, password=None):
        if url[-1] == '/':
            self.server = url
        else:
            self.server = url + '/'

        self.auth_headers = None

        if username is not None and password is not None:
            self.auth_headers = aiohttp.BasicAuth(username, password).encode()

    @property
    def headers(self):
        if self.auth_headers:
            return {u'Authorization': self.auth_headers}

    def build_url(self, path):
        return u'{}{}'.format(self.server, path)

    async def _perform_get_request(self, url):
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            try:
                async with session.get(url=url, headers=self.headers) as resp:
                    return await resp.json()
            except ClientResponseError as e:
                if e.code == 404:
                    raise NotFoundException(
                        'Requested item could not be found'
                    )
                elif e.code in [401, 403, 500]:
                    raise JenkinsException(
                        ('Error in request. Possibly '
                         'authentication failed [{}]: {}').format(
                            e.code, e.message)
                    )
                else:
                    raise

    async def _perform_post_request(self, url, data=None):
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            try:
                async with session.post(url=url, data=data, headers=self.headers) as resp:
                    return await resp.json()
            except ClientResponseError as e:
                if e.code == 404:
                    raise NotFoundException(
                        'Requested item could not be found'
                    )
                elif e.code in [401, 403, 500]:
                    raise JenkinsException(
                        ('Error in request. Possibly '
                         'authentication failed [{}]: {}').format(
                            e.code, e.message)
                    )
                else:
                    raise

    async def job_exists(self, name):
        url = self.build_url(JOB_NAME.format(job_name=name))
        try:
            response = await self._perform_get_request(url)
            return response[u'name'] == name
        except NotFoundException as e:
            return False

    async def get_job_info(self, name, depth=0):
        url = self.build_url(JOB_INFO.format(job_name=name, depth=depth))
        return await self._perform_get_request(url)

    async def get_next_build_number(self, name):
        response = await self.get_job_info(name)
        return response[u'nextBuildNumber']

    async def get_build_info(self, name, number, depth=0):
        url = self.build_url(
            BUILD_INFO.format(job_name=name, number=number, depth=depth)
        )
        return await self._perform_get_request(url)

    async def wait_until_build_exist(self, name, number, timeout=10):
        start_time = time.time()
        while True:
            try:
                return await self.get_build_info(name, number)
            except NotFoundException as e:
                if time.time() - start_time > timeout:
                    raise

    async def build_job(self, name, params=None):
        if params:
            path = BUILD_WITH_PARAMS_JOB.format(
                job_name=name, params=urlencode(params)
            )
        else:
            path = BUILD_JOB.format(job_name=name)

        url = self.build_url(path)
        return await self._perform_post_request(url)

