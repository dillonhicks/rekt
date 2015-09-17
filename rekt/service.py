import sys
import imp
import itertools
import collections.abc
import pathlib
import concurrent.futures

from collections import namedtuple, deque

import requests
import yaml

if sys.version_info >= (3, 5):
    from http import HTTPStatus
elif sys.version_info >= (3, 4):
    from rekt.httputils import HTTPStatus
else:
    raise RuntimeError('Unsupported python version: {}'.format(sys.version_info))

from rekt.httputils import HTTPVerb, ArgsLocation, _ARGS_LOCATION_BY_VERB
from rekt.utils import (_NULL_OBJECT, read_only_dict, camel_case_to_snake_case, load_config,
                        api_method_name, async_api_method_name)

__all__ = ['load_service']

_RESOURCE_NAME_FMT = '{}Resource'
_RESOURCE_ATTRIBUTES = ('name', 'url', 'actions', 'request_classes', 'response_classes')
_REQUEST_NAME_FMT = '{}{}Request'
_RESPONSE_NAME_FMT = '{}{}Response'

# TODO: make configurable in the client
_ASYNC_WORKER_THREAD_COUNT = 6

class DynamicObject(dict):
    """
    Base class for all response types. It acts like hybrid between a
    . attribute access object and a defaultdict(lambda: None) meaning
    that any .<attributename> that does not exist in the backing
    dictionary will be guaranteed to return None.

    Inspired by and similar to Groovy's Expando object.
    """
    # Recipe for allowing . attribute access on a dictionary from
    # http://stackoverflow.com/questions/4984647/accessing-dict-keys-like-an-attribute-in-python
    def __init__(self, *args, **kwargs):
        super(DynamicObject, self).__init__(*args, **kwargs)
        self.__dict__ = self

    def __getattr__(self, key):
        return self[key]

    def __missing__(self, key):
        return None

    def __reduce__(self):
        return (dict, (), self.__getstate__())

    def __getstate__(self):
        return dict(self)

    def __setstate__(self, state):
        self.update(state)

    def __str__(self):
        return yaml.dump(dict(self), canonical=False, default_flow_style=False, encoding=None)


class RestClient(object):
    """
    Class for convenience off of which we will dynamically create
    the rest client
    """
    def __str__(self):
        return '{}'.format(self.__class__.__name__)

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)


def create_request_class(api, verb, args, defaults):
    """
    """
    signature = deque()

    # Modify the parameters of the signature such that those
    # with defaults follow those without
    for arg in args:
        if arg in defaults.keys():
            signature.append(arg)
        else:
            signature.appendleft(arg)

    signature = tuple(signature)

    default_values = []

    for arg, value in sorted(defaults.items(), key=lambda x: signature.index(x[0])):
        try:
            index = signature.index(arg)
        except ValueError:
            raise RuntimeError('Not able to find argument: {}'.format(arg))

        default_values.append(value)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            # here, the argnames variable is the one passed to the
            # ClassFactory call
            if key not in signature:
                raise TypeError("Argument %s not valid for %s"
                                % (key, self.__class__.__name__))
            setattr(self, key, value)

        BaseClass.__init__(self, _REQUEST_NAME_FMT.format(verb.name.title(), name))

    RequestClass = type(_REQUEST_NAME_FMT.format(verb.name.title(), api), (DynamicObject,), {})
    return RequestClass


def create_response_class(api, verb):
    """
    """
    ResponseClass = type(_RESPONSE_NAME_FMT.format(verb.name.title(), api), (DynamicObject,), {})
    return ResponseClass


def create_api_definition(api, defn, baseurl):

    ResourceClass = namedtuple(_RESOURCE_NAME_FMT.format(api), _RESOURCE_ATTRIBUTES)

    actions = []
    request_classes = {}
    response_classes = {}

    for verb in HTTPVerb:
        if defn.get(verb.name, None) is None:
            continue

        defaults = dict([(k, v['default']) for k,v in defn[verb.name].items()
                         if v is not None
                         and isinstance(v, dict)
                         and v.get('default', _NULL_OBJECT) is not _NULL_OBJECT])

        actions.append(verb)
        request_classes[verb] = create_request_class(api, verb, defn[verb.name].keys(), defaults)
        response_classes[verb] = create_response_class(api, verb)


    return ResourceClass(api, baseurl + defn['url'], actions, request_classes, response_classes)


def create_api_call_func(api, verb):
    """
    From an api definition object create the related api call method
    that will validate the arguments for the api call and then
    dynamically dispatch the request to the appropriate requests module
    convenience method for the specific HTTP verb .
    """

    # Scopes some local context in which we can build
    # request functions with reflection that primed with
    # some static parameters.
    def api_call_func(self, **kwargs):

        request = api.request_classes[verb](**kwargs)
        params = dict([ (k,v) for k,v in request.items() if v is not None ])


        if HTTPVerb.GET == verb:
            raw_response = requests.get(api.url, params=params, **self.reqargs)

        elif HTTPVerb.POST == verb:
            raw_response = requests.post(api.url, data=params, **self.reqargs)

        else:
            raise RuntimeError('{} is not a handled http verb'.format(verb))

        if raw_response.status_code != HTTPStatus.OK:
            raw_response.raise_for_status()

        # The object hook will convert all dictionaries from the json
        # objects in the response to a . attribute access
        response = raw_response.json(object_hook=lambda obj: api.response_classes[verb](obj))
        return response

    method_name = api_method_name(verb, api)

    api_call_func.__name__ = method_name
    api_call_func.__doc__ = "{}\nParameters:\n  {}".format(
        method_name, '\n  '.join(api.request_classes[verb]().keys()))

    return api_call_func


def create_async_api_call_func(api, verb):
    """
    From an api definition object create the related api call method
    that will validate the arguments for the api call and then
    dynamically dispatch the request to the appropriate requests module
    convenience method for the specific HTTP verb .
    """

    # Scopes some local context in which we can build
    # request functions with reflection that primed with
    # some static parameters.
    def api_call_func(self, **kwargs):

        def _async_call_handler():
            request = api.request_classes[verb](**kwargs)
            params = dict([ (k,v) for k,v in request.items() if v is not None ])


            if HTTPVerb.GET == verb:
                raw_response = requests.get(api.url, params=params, **self.reqargs)

            elif HTTPVerb.POST == verb:
                raw_response = requests.post(api.url, data=params, **self.reqargs)

            else:
                raise RuntimeError('{} is not a handled http verb'.format(verb))

            if raw_response.status_code != HTTPStatus.OK:
                raw_response.raise_for_status()

            # The object hook will convert all dictionaries from the json
            # objects in the response to a . attribute access
            response = raw_response.json(object_hook=lambda obj: api.response_classes[verb](obj))
            return response

        call_handler_name = '_async_handler_for_' + camel_case_to_snake_case(verb.name + api.name)
        _async_call_handler.__name__ = call_handler_name

        return self._executor.submit(_async_call_handler)

    method_name = async_api_method_name(verb, api)

    api_call_func.__name__ = method_name
    api_call_func.__doc__ = "{}\nParameters:\n  {}".format(
        method_name, '\n  '.join(api.request_classes[verb]().keys()))

    return api_call_func



def create_rest_client_class(name, apis, BaseClass=RestClient):
    """
    Generate the api call functions and attach them to the generated
    RestClient subclass with the name <Service>Client.
    """

    apis_with_actions = list(itertools.chain.from_iterable([ zip([api] * len(api.actions), api.actions) for api in apis]))

    api_funcs = [create_api_call_func(api, verb) for api, verb in apis_with_actions]
    api_funcs.extend([create_async_api_call_func(api, verb) for api, verb in apis_with_actions])
    api_mapper = dict([ (f.__name__, f) for f in api_funcs ])

    # Adapted from :
    # http://stackoverflow.com/questions/15247075/how-can-i-dynamically-create-derived-classes-from-a-base-class
    def __init__(self, **reqargs):
        BaseClass.__init__(self)
        setattr(self, 'reqargs', read_only_dict(reqargs))
        self._executor = concurrent.futures.ThreadPoolExecutor(_ASYNC_WORKER_THREAD_COUNT)

    api_mapper['__init__'] =  __init__

    ClientClass = type('{}Client'.format(name), (BaseClass,), api_mapper)
    return ClientClass


def create_service_module(service_name, apis):
   """
   Dynamically creates a module named defined by the PEP-8 version of
   the string contained in service_name (from the YAML config). This
   module will contain a Client class, a Call Factory, and list of API
   definition objects.
   """
   service_module = imp.new_module(service_name.lower())

   for api in apis:
      setattr(service_module, api.__class__.__name__, api)

   ClientClass = create_rest_client_class(service_name, apis)

   setattr(service_module, 'resources', tuple(apis))
   setattr(service_module, 'Client', ClientClass)

   sys.modules[service_name.lower()] = service_module
   return service_module


def load_service(config):
   """
   Load a restful service specified by some YAML file at config_path.

   :param config_path: A pathlib Path object that points to the yaml
       config
   :returns: A python module containing a Client class, call factory,
       and the definition of each of the APIs defined by the config.
   """
   if isinstance(config, collections.abc.Mapping):
       service_config = config
   elif isinstance(config, str):
       service_config = load_config(pathlib.Path(config))
   elif isinstance(config, pathlib.Path):
       service_config = load_config(config)
   else:
       raise TypeError('Cannot load config from type: {}'.format(type(config)))

   apis = []
   for api, defn in service_config['apis'].items():
       api_def= create_api_definition(api, defn, service_config['base_url'])
       apis.append(api_def)

   service_module = create_service_module(service_config['name'], apis)
   return service_module
