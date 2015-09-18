import re
import types
import collections
import pathlib

from collections import defaultdict, OrderedDict
from itertools import chain
from pathlib import Path, PurePath

from pkg_resources import resource_filename
import yaml

from . import specs

__all__ = [
    'read_only_dict',
    'load_builtin_config',
    'load_config',
    'api_method_name',
    'async_api_method_name',
    'api_method_names',
]

# Kept as a way to safely do .get() but allow a None reference
_NULL_OBJECT = object()
_ASYNC_METHOD_PREFIX = 'async_'

def read_only_dict(mapping):
    return types.MappingProxyType(mapping)

_FIRST_CAP_RE = re.compile('(.)([A-Z][a-z]+)')
_ALL_CAP_RE = re.compile('([a-z0-9])([A-Z])')
def camel_case_to_snake_case(name):
    """
    HelloWorld -> hello_world
    """
    s1 = _FIRST_CAP_RE.sub(r'\1_\2', name)
    return _ALL_CAP_RE.sub(r'\1_\2', s1).lower()

def snake_case_to_camel_case(name):
    """
    hello_world -> HelloWorld
    """
    return name.replace('_', ' ').title().replace(' ', '')


def load_builtin_config(name, module_name=__name__):
    """
    Uses package info magic to find the resource file located in the specs
    submodule.
    """
    config_path = Path(next(iter(specs.__path__)))
    config_path = config_path / PurePath(resource_filename(module_name, name + '.yaml'))
    return load_config(config_path)

def load_config(path):
   """
   Loads a yaml configuration.

   :param path: a pathlib Path object pointing to the configuration
   """
   with path.open('rb') as fi:
       file_bytes = fi.read()
       config = yaml.load(file_bytes.decode('utf-8'))

   return config

def api_method_name(verb, resource):
    """
    Create a canonical python method name for a synchronous request
    method by combining the http verb name and the resource name.
    """
    return camel_case_to_snake_case(verb.name + resource.name)


def async_api_method_name(verb, resource):
    """
    Create a canonical python method name for a synchronous request
    method by combining the http verb name and the resource name with the
    async method prefix.
    """
    return _ASYNC_METHOD_PREFIX + api_method_name(verb, resource)


def api_method_names(resources):
    api_methods = [[api_method_name(verb, rsrc) for verb in rsrc.actions] for rsrc in resources]
    api_methods.extend([[async_api_method_name(verb, rsrc) for verb in rsrc.actions] for rsrc in resources])
    api_methods = chain.from_iterable(api_methods)
    return api_methods


def load_swagger_config(name, base_url, config):
   """
   Load a restful service specified by some YAML file at config_path.

   :param config_path: A pathlib Path object that points to the yaml
       config
   :returns: A python module containing a Client class, call factory,
       and the definition of each of the APIs defined by the config.
   """
   if isinstance(config, collections.abc.Mapping):
       pass
   elif isinstance(config, str):
       with pathlib.Path(config).open('r') as infile:
           config = yaml.load(infile)

   elif isinstance(config, pathlib.Path):
       with config.open('r') as infile:
           config = yaml.load(infile)

   else:
       raise TypeError('Cannot load swagger config from type: {}'.format(type(config)))


   service_config = dict([
           ('name', name), ('base_url', base_url), ('apis', defaultdict(dict))])

   apis = config['apis']


   for api in apis:
       # /some/path/to/my_resource -> MyResource
       resource = snake_case_to_camel_case(api['path'].rsplit('/', 1)[-1])
       for op in api['operations']:
           verb = op['method'].upper()
           args = [(param['name'], {'default' : None}) for param in op['parameters']
                   if param['paramType'].lower() != 'header']

           definition = dict([
              ('url',  api['path']),
              (verb, dict(args))
               ])

           service_config['apis'][resource].update(definition)

   return service_config
