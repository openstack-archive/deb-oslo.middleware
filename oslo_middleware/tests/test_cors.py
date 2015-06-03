# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg
from oslo_config import fixture
from oslotest import base as test_base
import webob
import webob.dec

from oslo_middleware import cors


class CORSTestBase(test_base.BaseTestCase):
    """Base class for all CORS tests.

    Sets up applications and helper methods.
    """

    def assertCORSResponse(self, response,
                           status='200 OK',
                           allow_origin=None,
                           max_age=None,
                           allow_methods=None,
                           allow_headers=None,
                           allow_credentials=None,
                           expose_headers=None):
        """Test helper for CORS response headers.

        Assert all the headers in a given response. By default, we assume
        the response is empty.
        """

        # Assert response status.
        self.assertEqual(response.status, status)

        # Assert the Access-Control-Allow-Origin header.
        self.assertHeader(response,
                          'Access-Control-Allow-Origin',
                          allow_origin)

        # Assert the Access-Control-Max-Age header.
        self.assertHeader(response,
                          'Access-Control-Max-Age',
                          max_age)

        # Assert the Access-Control-Allow-Methods header.
        self.assertHeader(response,
                          'Access-Control-Allow-Methods',
                          allow_methods)

        # Assert the Access-Control-Allow-Headers header.
        self.assertHeader(response,
                          'Access-Control-Allow-Headers',
                          allow_headers)

        # Assert the Access-Control-Allow-Credentials header.
        self.assertHeader(response,
                          'Access-Control-Allow-Credentials',
                          allow_credentials)

        # Assert the Access-Control-Expose-Headers header.
        self.assertHeader(response,
                          'Access-Control-Expose-Headers',
                          expose_headers)

        # If we're expecting an origin response, also assert that the
        # Vary: Origin header is set, since this implementation of the CORS
        # specification permits multiple origin domains.
        if allow_origin:
            self.assertHeader(response, 'Vary', 'Origin')

    def assertHeader(self, response, header, value=None):
        if value:
            self.assertIn(header, response.headers)
            self.assertEqual(str(value),
                             response.headers[header])
        else:
            self.assertNotIn(header, response.headers)


class CORSRegularRequestTest(CORSTestBase):
    """CORS Specification Section 6.1

    http://www.w3.org/TR/cors/#resource-requests
    """

    # List of HTTP methods (other than OPTIONS) to test with.
    methods = ['POST', 'PUT', 'DELETE', 'GET', 'TRACE', 'HEAD']

    def setUp(self):
        """Setup the tests."""
        super(CORSRegularRequestTest, self).setUp()

        @webob.dec.wsgify
        def application(req):
            return 'Hello, World!!!'

        # Set up the config fixture.
        config = self.useFixture(fixture.Config(cfg.CONF))

        config.load_raw_values(group='cors',
                               allowed_origin='http://valid.example.com',
                               allow_credentials='False',
                               max_age='',
                               expose_headers='',
                               allow_methods='GET',
                               allow_headers='')

        config.load_raw_values(group='cors.credentials',
                               allowed_origin='http://creds.example.com',
                               allow_credentials='True')

        config.load_raw_values(group='cors.exposed-headers',
                               allowed_origin='http://headers.example.com',
                               expose_headers='X-Header-1,X-Header-2',
                               allow_headers='X-Header-1,X-Header-2')

        config.load_raw_values(group='cors.cached',
                               allowed_origin='http://cached.example.com',
                               max_age='3600')

        config.load_raw_values(group='cors.get-only',
                               allowed_origin='http://get.example.com',
                               allow_methods='GET')
        config.load_raw_values(group='cors.all-methods',
                               allowed_origin='http://all.example.com',
                               allow_methods='GET,PUT,POST,DELETE,HEAD')

        # Now that the config is set up, create our application.
        self.application = cors.CORS(application, cfg.CONF)

    def test_config_overrides(self):
        """Assert that the configuration options are properly registered."""

        # Confirm global configuration
        gc = cfg.CONF.cors
        self.assertEqual(gc.allowed_origin, 'http://valid.example.com')
        self.assertEqual(gc.allow_credentials, False)
        self.assertEqual(gc.expose_headers, [])
        self.assertEqual(gc.max_age, None)
        self.assertEqual(gc.allow_methods, ['GET'])
        self.assertEqual(gc.allow_headers, [])

        # Confirm credentials overrides.
        cc = cfg.CONF['cors.credentials']
        self.assertEqual(cc.allowed_origin, 'http://creds.example.com')
        self.assertEqual(cc.allow_credentials, True)
        self.assertEqual(cc.expose_headers, gc.expose_headers)
        self.assertEqual(cc.max_age, gc.max_age)
        self.assertEqual(cc.allow_methods, gc.allow_methods)
        self.assertEqual(cc.allow_headers, gc.allow_headers)

        # Confirm exposed-headers overrides.
        ec = cfg.CONF['cors.exposed-headers']
        self.assertEqual(ec.allowed_origin, 'http://headers.example.com')
        self.assertEqual(ec.allow_credentials, gc.allow_credentials)
        self.assertEqual(ec.expose_headers, ['X-Header-1', 'X-Header-2'])
        self.assertEqual(ec.max_age, gc.max_age)
        self.assertEqual(ec.allow_methods, gc.allow_methods)
        self.assertEqual(ec.allow_headers, ['X-Header-1', 'X-Header-2'])

        # Confirm cached overrides.
        chc = cfg.CONF['cors.cached']
        self.assertEqual(chc.allowed_origin, 'http://cached.example.com')
        self.assertEqual(chc.allow_credentials, gc.allow_credentials)
        self.assertEqual(chc.expose_headers, gc.expose_headers)
        self.assertEqual(chc.max_age, 3600)
        self.assertEqual(chc.allow_methods, gc.allow_methods)
        self.assertEqual(chc.allow_headers, gc.allow_headers)

        # Confirm get-only overrides.
        goc = cfg.CONF['cors.get-only']
        self.assertEqual(goc.allowed_origin, 'http://get.example.com')
        self.assertEqual(goc.allow_credentials, gc.allow_credentials)
        self.assertEqual(goc.expose_headers, gc.expose_headers)
        self.assertEqual(goc.max_age, gc.max_age)
        self.assertEqual(goc.allow_methods, ['GET'])
        self.assertEqual(goc.allow_headers, gc.allow_headers)

        # Confirm all-methods overrides.
        ac = cfg.CONF['cors.all-methods']
        self.assertEqual(ac.allowed_origin, 'http://all.example.com')
        self.assertEqual(ac.allow_credentials, gc.allow_credentials)
        self.assertEqual(ac.expose_headers, gc.expose_headers)
        self.assertEqual(ac.max_age, gc.max_age)
        self.assertEqual(ac.allow_methods,
                         ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'])
        self.assertEqual(ac.allow_headers, gc.allow_headers)

    def test_no_origin_header(self):
        """CORS Specification Section 6.1.1

        If the Origin header is not present terminate this set of steps. The
        request is outside the scope of this specification.
        """
        for method in self.methods:
            request = webob.Request({})
            request.method = method
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin=None,
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

    def test_origin_headers(self):
        """CORS Specification Section 6.1.2

        If the value of the Origin header is not a case-sensitive match for
        any of the values in list of origins, do not set any additional
        headers and terminate this set of steps.
        """

        # Test valid origin header.
        for method in self.methods:
            request = webob.Request({})
            request.method = method
            request.headers['Origin'] = 'http://valid.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://valid.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

        # Test origin header not present in configuration.
        for method in self.methods:
            request = webob.Request({})
            request.method = method
            request.headers['Origin'] = 'http://invalid.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin=None,
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

        # Test valid, but case-mismatched origin header.
        for method in self.methods:
            request = webob.Request({})
            request.method = method
            request.headers['Origin'] = 'http://VALID.EXAMPLE.COM'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin=None,
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

    def test_supports_credentials(self):
        """CORS Specification Section 6.1.3

        If the resource supports credentials add a single
        Access-Control-Allow-Origin header, with the value of the Origin header
        as value, and add a single Access-Control-Allow-Credentials header with
        the case-sensitive string "true" as value.

        Otherwise, add a single Access-Control-Allow-Origin header, with
        either the value of the Origin header or the string "*" as value.

        NOTE: We never use the "*" as origin.
        """
        # Test valid origin header without credentials.
        for method in self.methods:
            request = webob.Request({})
            request.method = method
            request.headers['Origin'] = 'http://valid.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://valid.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

        # Test valid origin header with credentials
        for method in self.methods:
            request = webob.Request({})
            request.method = method
            request.headers['Origin'] = 'http://creds.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://creds.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials="true",
                                    expose_headers=None)

    def test_expose_headers(self):
        """CORS Specification Section 6.1.4

        If the list of exposed headers is not empty add one or more
        Access-Control-Expose-Headers headers, with as values the header field
        names given in the list of exposed headers.
        """
        for method in self.methods:
            request = webob.Request({})
            request.method = method
            request.headers['Origin'] = 'http://headers.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://headers.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers='X-Header-1,X-Header-2')


class CORSPreflightRequestTest(CORSTestBase):
    """CORS Specification Section 6.2

    http://www.w3.org/TR/cors/#resource-preflight-requests
    """

    def setUp(self):
        super(CORSPreflightRequestTest, self).setUp()

        @webob.dec.wsgify
        def application(req):
            return 'Hello, World!!!'

        # Set up the config fixture.
        config = self.useFixture(fixture.Config(cfg.CONF))

        config.load_raw_values(group='cors',
                               allowed_origin='http://valid.example.com',
                               allow_credentials='False',
                               max_age='',
                               expose_headers='',
                               allow_methods='GET',
                               allow_headers='')

        config.load_raw_values(group='cors.credentials',
                               allowed_origin='http://creds.example.com',
                               allow_credentials='True')

        config.load_raw_values(group='cors.exposed-headers',
                               allowed_origin='http://headers.example.com',
                               expose_headers='X-Header-1,X-Header-2',
                               allow_headers='X-Header-1,X-Header-2')

        config.load_raw_values(group='cors.cached',
                               allowed_origin='http://cached.example.com',
                               max_age='3600')

        config.load_raw_values(group='cors.get-only',
                               allowed_origin='http://get.example.com',
                               allow_methods='GET')
        config.load_raw_values(group='cors.all-methods',
                               allowed_origin='http://all.example.com',
                               allow_methods='GET,PUT,POST,DELETE,HEAD')

        # Now that the config is set up, create our application.
        self.application = cors.CORS(application, cfg.CONF)

    def test_config_overrides(self):
        """Assert that the configuration options are properly registered."""

        # Confirm global configuration
        gc = cfg.CONF.cors
        self.assertEqual(gc.allowed_origin, 'http://valid.example.com')
        self.assertEqual(gc.allow_credentials, False)
        self.assertEqual(gc.expose_headers, [])
        self.assertEqual(gc.max_age, None)
        self.assertEqual(gc.allow_methods, ['GET'])
        self.assertEqual(gc.allow_headers, [])

        # Confirm credentials overrides.
        cc = cfg.CONF['cors.credentials']
        self.assertEqual(cc.allowed_origin, 'http://creds.example.com')
        self.assertEqual(cc.allow_credentials, True)
        self.assertEqual(cc.expose_headers, gc.expose_headers)
        self.assertEqual(cc.max_age, gc.max_age)
        self.assertEqual(cc.allow_methods, gc.allow_methods)
        self.assertEqual(cc.allow_headers, gc.allow_headers)

        # Confirm exposed-headers overrides.
        ec = cfg.CONF['cors.exposed-headers']
        self.assertEqual(ec.allowed_origin, 'http://headers.example.com')
        self.assertEqual(ec.allow_credentials, gc.allow_credentials)
        self.assertEqual(ec.expose_headers, ['X-Header-1', 'X-Header-2'])
        self.assertEqual(ec.max_age, gc.max_age)
        self.assertEqual(ec.allow_methods, gc.allow_methods)
        self.assertEqual(ec.allow_headers, ['X-Header-1', 'X-Header-2'])

        # Confirm cached overrides.
        chc = cfg.CONF['cors.cached']
        self.assertEqual(chc.allowed_origin, 'http://cached.example.com')
        self.assertEqual(chc.allow_credentials, gc.allow_credentials)
        self.assertEqual(chc.expose_headers, gc.expose_headers)
        self.assertEqual(chc.max_age, 3600)
        self.assertEqual(chc.allow_methods, gc.allow_methods)
        self.assertEqual(chc.allow_headers, gc.allow_headers)

        # Confirm get-only overrides.
        goc = cfg.CONF['cors.get-only']
        self.assertEqual(goc.allowed_origin, 'http://get.example.com')
        self.assertEqual(goc.allow_credentials, gc.allow_credentials)
        self.assertEqual(goc.expose_headers, gc.expose_headers)
        self.assertEqual(goc.max_age, gc.max_age)
        self.assertEqual(goc.allow_methods, ['GET'])
        self.assertEqual(goc.allow_headers, gc.allow_headers)

        # Confirm all-methods overrides.
        ac = cfg.CONF['cors.all-methods']
        self.assertEqual(ac.allowed_origin, 'http://all.example.com')
        self.assertEqual(ac.allow_credentials, gc.allow_credentials)
        self.assertEqual(ac.expose_headers, gc.expose_headers)
        self.assertEqual(ac.max_age, gc.max_age)
        self.assertEqual(ac.allow_methods,
                         ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'])
        self.assertEqual(ac.allow_headers, gc.allow_headers)

    def test_no_origin_header(self):
        """CORS Specification Section 6.2.1

        If the Origin header is not present terminate this set of steps. The
        request is outside the scope of this specification.
        """
        request = webob.Request({})
        request.method = "OPTIONS"
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_case_sensitive_origin(self):
        """CORS Specification Section 6.2.2

        If the value of the Origin header is not a case-sensitive match for
        any of the values in list of origins do not set any additional headers
        and terminate this set of steps.
        """

        # Test valid domain
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://valid.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://valid.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers='',
                                allow_credentials=None,
                                expose_headers=None)

        # Test invalid domain
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://invalid.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

        # Test case-sensitive mismatch domain
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://VALID.EXAMPLE.COM'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_no_request_method(self):
        """CORS Specification Section 6.2.3

        If there is no Access-Control-Request-Method header or if parsing
        failed, do not set any additional headers and terminate this set of
        steps. The request is outside the scope of this specification.
        """

        # Test valid domain, valid method.
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://get.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://get.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

        # Test valid domain, invalid HTTP method.
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://valid.example.com'
        request.headers['Access-Control-Request-Method'] = 'TEAPOT'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

        # Test valid domain, no HTTP method.
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://valid.example.com'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_invalid_method(self):
        """CORS Specification Section 6.2.3

        If method is not a case-sensitive match for any of the values in
        list of methods do not set any additional headers and terminate this
        set of steps.
        """
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://get.example.com'
        request.headers['Access-Control-Request-Method'] = 'get'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_no_parse_request_headers(self):
        """CORS Specification Section 6.2.4

        If there are no Access-Control-Request-Headers headers let header
        field-names be the empty list.

        If parsing failed do not set any additional headers and terminate
        this set of steps. The request is outside the scope of this
        specification.
        """
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = 'value with spaces'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_no_request_headers(self):
        """CORS Specification Section 6.2.4

        If there are no Access-Control-Request-Headers headers let header
        field-names be the empty list.
        """
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = ''
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://headers.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_request_headers(self):
        """CORS Specification Section 6.2.4

        Let header field-names be the values as result of parsing the
        Access-Control-Request-Headers headers.

        If there are no Access-Control-Request-Headers headers let header
        field-names be the empty list.
        """
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = 'X-Header-1,' \
                                                            'X-Header-2'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://headers.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers='X-Header-1,X-Header-2',
                                allow_credentials=None,
                                expose_headers=None)

    def test_request_headers_not_permitted(self):
        """CORS Specification Section 6.2.4, 6.2.6

        If there are no Access-Control-Request-Headers headers let header
        field-names be the empty list.

        If any of the header field-names is not a ASCII case-insensitive
        match for any of the values in list of headers do not set any
        additional headers and terminate this set of steps.
        """
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = 'X-Not-Exposed,' \
                                                            'X-Never-Exposed'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_credentials(self):
        """CORS Specification Section 6.2.7

        If the resource supports credentials add a single
        Access-Control-Allow-Origin header, with the value of the Origin header
        as value, and add a single Access-Control-Allow-Credentials header with
        the case-sensitive string "true" as value.

        Otherwise, add a single Access-Control-Allow-Origin header, with either
        the value of the Origin header or the string "*" as value.

        NOTE: We never use the "*" as origin.
        """
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://creds.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://creds.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials="true",
                                expose_headers=None)

    def test_optional_max_age(self):
        """CORS Specification Section 6.2.8

        Optionally add a single Access-Control-Max-Age header with as value
        the amount of seconds the user agent is allowed to cache the result of
        the request.
        """
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://cached.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://cached.example.com',
                                max_age=3600,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_allow_methods(self):
        """CORS Specification Section 6.2.9

        Add one or more Access-Control-Allow-Methods headers consisting of
        (a subset of) the list of methods.

        Since the list of methods can be unbounded, simply returning the method
        indicated by Access-Control-Request-Method (if supported) can be
        enough.
        """
        for method in ['GET', 'PUT', 'POST', 'DELETE']:
            request = webob.Request({})
            request.method = "OPTIONS"
            request.headers['Origin'] = 'http://all.example.com'
            request.headers['Access-Control-Request-Method'] = method
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://all.example.com',
                                    max_age=None,
                                    allow_methods=method,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

        for method in ['PUT', 'POST', 'DELETE']:
            request = webob.Request({})
            request.method = "OPTIONS"
            request.headers['Origin'] = 'http://get.example.com'
            request.headers['Access-Control-Request-Method'] = method
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin=None,
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

    def test_allow_headers(self):
        """CORS Specification Section 6.2.10

        Add one or more Access-Control-Allow-Headers headers consisting of
        (a subset of) the list of headers.

        If each of the header field-names is a simple header and none is
        Content-Type, this step may be skipped.

        If a header field name is a simple header and is not Content-Type, it
        is not required to be listed. Content-Type is to be listed as only a
        subset of its values makes it qualify as simple header.
        """

        requested_headers = 'Content-Type,X-Header-1,Cache-Control,Expires,' \
                            'Last-Modified,Pragma'

        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = requested_headers
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://headers.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=requested_headers,
                                allow_credentials=None,
                                expose_headers=None)


class CORSTestWildcard(CORSTestBase):
    """Test the CORS wildcard specification."""

    def setUp(self):
        super(CORSTestWildcard, self).setUp()

        @webob.dec.wsgify
        def application(req):
            return 'Hello, World!!!'

        # Set up the config fixture.
        config = self.useFixture(fixture.Config(cfg.CONF))

        config.load_raw_values(group='cors',
                               allowed_origin='http://default.example.com',
                               allow_credentials='True',
                               max_age='',
                               expose_headers='',
                               allow_methods='GET,PUT,POST,DELETE,HEAD',
                               allow_headers='')

        config.load_raw_values(group='cors.wildcard',
                               allowed_origin='*',
                               allow_methods='GET')

        # Now that the config is set up, create our application.
        self.application = cors.CORS(application, cfg.CONF)

    def test_config_overrides(self):
        """Assert that the configuration options are properly registered."""

        # Confirm global configuration
        gc = cfg.CONF.cors
        self.assertEqual(gc.allowed_origin, 'http://default.example.com')
        self.assertEqual(gc.allow_credentials, True)
        self.assertEqual(gc.expose_headers, [])
        self.assertEqual(gc.max_age, None)
        self.assertEqual(gc.allow_methods, ['GET', 'PUT', 'POST', 'DELETE',
                                            'HEAD'])
        self.assertEqual(gc.allow_headers, [])

        # Confirm all-methods overrides.
        ac = cfg.CONF['cors.wildcard']
        self.assertEqual(ac.allowed_origin, '*')
        self.assertEqual(gc.allow_credentials, True)
        self.assertEqual(ac.expose_headers, gc.expose_headers)
        self.assertEqual(ac.max_age, gc.max_age)
        self.assertEqual(ac.allow_methods, ['GET'])
        self.assertEqual(ac.allow_headers, gc.allow_headers)

    def test_wildcard_domain(self):
        """CORS Specification, Wildcards

        If the configuration file specifies CORS settings for the wildcard '*'
        domain, it should return those for all origin domains except for the
        overrides.
        """

        # Test valid domain
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://default.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://default.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers='',
                                allow_credentials='true',
                                expose_headers=None)

        # Test invalid domain
        request = webob.Request({})
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://invalid.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='*',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers='',
                                allow_credentials='true',
                                expose_headers=None)
