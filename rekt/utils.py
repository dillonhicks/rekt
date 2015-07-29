import re
import types
import collections

from pkg_resources import resource_filename
from pathlib import Path, PurePath

import yaml

from . import specs

# Kept as a way to safely do .get() but allow a None reference
_NULL_OBJECT = object()

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

def load_builtin_config(name):
    if isinstance(specs.__path__, collections.Iterable):
        config_path = Path(specs.__path__[0])
    else:
        config_path = Path(specs__path__._path[0])

    config_path = config_path / PurePath(resource_filename('rekt.specs', name + '.yaml'))
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
