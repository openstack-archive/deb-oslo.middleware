# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing permissions and
# limitations under the License.

# Default allowed headers
import copy
import logging

from oslo_config import cfg
from oslo_middleware import base
import webob.dec
import webob.exc
import webob.response


LOG = logging.getLogger(__name__)

CORS_OPTS = [
    cfg.StrOpt('allowed_origin',
               default=None,
               help='Indicate whether this resource may be shared with the '
                    'domain received in the requests "origin" header.'),
    cfg.BoolOpt('allow_credentials',
                default=True,
                help='Indicate that the actual request can include user '
                     'credentials'),
    cfg.ListOpt('expose_headers',
                default=['Content-Type', 'Cache-Control', 'Content-Language',
                         'Expires', 'Last-Modified', 'Pragma'],
                help='Indicate which headers are safe to expose to the API. '
                     'Defaults to HTTP Simple Headers.'),
    cfg.IntOpt('max_age',
               default=3600,
               help='Maximum cache age of CORS preflight requests.'),
    cfg.ListOpt('allow_methods',
                default=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
                help='Indicate which methods can be used during the actual '
                     'request.'),
    cfg.ListOpt('allow_headers',
                default=['Content-Type', 'Cache-Control', 'Content-Language',
                         'Expires', 'Last-Modified', 'Pragma'],
                help='Indicate which header field names may be used during '
                     'the actual request.')
]


def filter_factory(global_conf,
                   allowed_origin,
                   allow_credentials=True,
                   expose_headers=None,
                   max_age=None,
                   allow_methods=None,
                   allow_headers=None):
    '''Factory to support paste.deploy

    :param global_conf: The paste.ini global configuration object (not used).
    :param allowed_origin: Protocol, host, and port for the allowed origin.
    :param allow_credentials: Whether to permit credentials.
    :param expose_headers: A list of headers to expose.
    :param max_age: Maximum cache duration.
    :param allow_methods: List of HTTP methods to permit.
    :param allow_headers: List of HTTP headers to permit from the client.
    :return:
    '''

    def filter(app):
        cors_app = CORS(app)
        cors_app.add_origin(allowed_origin=allowed_origin,
                            allow_credentials=allow_credentials,
                            expose_headers=expose_headers,
                            max_age=max_age,
                            allow_methods=allow_methods,
                            allow_headers=allow_headers)
        return cors_app

    return filter


class CORS(base.Middleware):
    """CORS Middleware.

    This middleware allows a WSGI app to serve CORS headers for multiple
    configured domains.

    For more information, see http://www.w3.org/TR/cors/
    """

    simple_headers = [
        'Content-Type',
        'Cache-Control',
        'Content-Language',
        'Expires',
        'Last-Modified',
        'Pragma'
    ]

    def __init__(self, application, conf=None):
        super(CORS, self).__init__(application)

        # Begin constructing our configuration hash.
        self.allowed_origins = {}

        # Sanity check. Do we have an oslo.config? If so, load it. Else, assume
        # that we'll use add_config.
        if conf:
            self._init_from_oslo(conf)

    def _init_from_oslo(self, conf):
        '''Initialize this middleware from an oslo.config instance.'''

        # First, check the configuration and register global options.
        conf.register_opts(CORS_OPTS, 'cors')

        # Clone our original CORS_OPTS, and set the defaults to whatever is
        # set in the global conf instance. This is done explicitly (instead
        # of **kwargs), since we don't accidentally want to catch
        # allowed_origin.
        subgroup_opts = copy.deepcopy(CORS_OPTS)
        cfg.set_defaults(subgroup_opts,
                         allow_credentials=conf.cors.allow_credentials,
                         expose_headers=conf.cors.expose_headers,
                         max_age=conf.cors.max_age,
                         allow_methods=conf.cors.allow_methods,
                         allow_headers=conf.cors.allow_headers)

        # If the default configuration contains an allowed_origin, don't
        # forget to register that.
        if conf.cors.allowed_origin:
            self.add_origin(**conf.cors)

        # Iterate through all the loaded config sections, looking for ones
        # prefixed with 'cors.'
        for section in conf.list_all_sections():
            if section.startswith('cors.'):
                # Register with the preconstructed defaults
                conf.register_opts(subgroup_opts, section)
                self.add_origin(**conf[section])

    def add_origin(self, allowed_origin, allow_credentials=True,
                   expose_headers=None, max_age=None, allow_methods=None,
                   allow_headers=None):
        '''Add another origin to this filter.

        :param allowed_origin: Protocol, host, and port for the allowed origin.
        :param allow_credentials: Whether to permit credentials.
        :param expose_headers: A list of headers to expose.
        :param max_age: Maximum cache duration.
        :param allow_methods: List of HTTP methods to permit.
        :param allow_headers: List of HTTP headers to permit from the client.
        :return:
        '''

        if allowed_origin in self.allowed_origins:
            LOG.warn('Allowed origin [%s] already exists, skipping' % (
                allowed_origin,))
            return

        self.allowed_origins[allowed_origin] = {
            'allow_credentials': allow_credentials,
            'expose_headers': expose_headers,
            'max_age': max_age,
            'allow_methods': allow_methods,
            'allow_headers': allow_headers
        }

    def process_response(self, response, request=None):
        '''Check for CORS headers, and decorate if necessary.

        Perform two checks. First, if an OPTIONS request was issued, let the
        application handle it, and (if necessary) decorate the response with
        preflight headers. In this case, if a 404 is thrown by the underlying
        application (i.e. if the underlying application does not handle
        OPTIONS requests, the response code is overridden.

        In the case of all other requests, regular request headers are applied.
        '''

        # Sanity precheck: If we detect CORS headers provided by something in
        # in the middleware chain, assume that it knows better.
        if 'Access-Control-Allow-Origin' in response.headers:
            return response

        # Doublecheck for an OPTIONS request.
        if request.method == 'OPTIONS':
            return self._apply_cors_preflight_headers(request=request,
                                                      response=response)

        # Apply regular CORS headers.
        self._apply_cors_request_headers(request=request, response=response)

        # Finally, return the response.
        return response

    def _split_header_values(self, request, header_name):
        """Convert a comma-separated header value into a list of values."""
        values = []
        if header_name in request.headers:
            for value in request.headers[header_name].rsplit(','):
                value = value.strip()
                if value:
                    values.append(value)
        return values

    def _apply_cors_preflight_headers(self, request, response):
        """Handle CORS Preflight (Section 6.2)

        Given a request and a response, apply the CORS preflight headers
        appropriate for the request.
        """

        # If the response contains a 2XX code, we have to assume that the
        # underlying middleware's response content needs to be persisted.
        # Otherwise, create a new response.
        if 200 > response.status_code or response.status_code >= 300:
            response = webob.response.Response(status=webob.exc.HTTPOk.code)

        # Does the request have an origin header? (Section 6.2.1)
        if 'Origin' not in request.headers:
            return response

        # Is this origin registered? (Section 6.2.2)
        origin = request.headers['Origin']
        if origin not in self.allowed_origins:
            if '*' in self.allowed_origins:
                origin = '*'
            else:
                LOG.debug('CORS request from origin \'%s\' not permitted.'
                          % (origin,))
                return response
        cors_config = self.allowed_origins[origin]

        # If there's no request method, exit. (Section 6.2.3)
        if 'Access-Control-Request-Method' not in request.headers:
            return response
        request_method = request.headers['Access-Control-Request-Method']

        # Extract Request headers. If parsing fails, exit. (Section 6.2.4)
        try:
            request_headers = \
                self._split_header_values(request,
                                          'Access-Control-Request-Headers')
        except Exception:
            LOG.debug('Cannot parse request headers.')
            return response

        # Compare request method to permitted methods (Section 6.2.5)
        if request_method not in cors_config['allow_methods']:
            return response

        # Compare request headers to permitted headers, case-insensitively.
        # (Section 6.2.6)
        for requested_header in request_headers:
            upper_header = requested_header.upper()
            permitted_headers = (cors_config['allow_headers'] +
                                 self.simple_headers)
            if upper_header not in (header.upper() for header in
                                    permitted_headers):
                return response

        # Set the default origin permission headers. (Sections 6.2.7, 6.4)
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Origin'] = origin

        # Does this CORS configuration permit credentials? (Section 6.2.7)
        if cors_config['allow_credentials']:
            response.headers['Access-Control-Allow-Credentials'] = 'true'

        # Attach Access-Control-Max-Age if appropriate. (Section 6.2.8)
        if 'max_age' in cors_config and cors_config['max_age']:
            response.headers['Access-Control-Max-Age'] = \
                str(cors_config['max_age'])

        # Attach Access-Control-Allow-Methods. (Section 6.2.9)
        response.headers['Access-Control-Allow-Methods'] = request_method

        # Attach  Access-Control-Allow-Headers. (Section 6.2.10)
        if request_headers:
            response.headers['Access-Control-Allow-Headers'] = \
                ','.join(request_headers)

        return response

    def _apply_cors_request_headers(self, request, response):
        """Handle Basic CORS Request (Section 6.1)

        Given a request and a response, apply the CORS headers appropriate
        for the request to the response.
        """

        # Does the request have an origin header? (Section 6.1.1)
        if 'Origin' not in request.headers:
            return

        # Is this origin registered? (Section 6.1.2)
        origin = request.headers['Origin']
        if origin not in self.allowed_origins:
            LOG.debug('CORS request from origin \'%s\' not permitted.'
                      % (origin,))
            return
        cors_config = self.allowed_origins[origin]

        # Set the default origin permission headers. (Sections 6.1.3 & 6.4)
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Origin'] = origin

        # Does this CORS configuration permit credentials? (Section 6.1.3)
        if cors_config['allow_credentials']:
            response.headers['Access-Control-Allow-Credentials'] = 'true'

        # Attach the exposed headers and exit. (Section 6.1.4)
        if cors_config['expose_headers']:
            response.headers['Access-Control-Expose-Headers'] = \
                ','.join(cors_config['expose_headers'])
