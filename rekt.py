# -*- coding: utf-8 -*-
"""
rekt
====

rekt is a wrapper around the requests library that makes generic rest
operations less painful. I was frustrated with the implementation of
many service speicific rest wrappers especially for google apis, this
library is meant to be generic and dynamic enough by templating the common
client code for most rest services.
"""
import argparse
import json
import imp
import sys
import types

from enum import Enum
from pprint import pformat
from collections import namedtuple, deque
from pathlib import PurePath, Path

import requests
import yaml

# Kept as a way to safely do .get() but allow a None reference
_NULL_OBJECT = object();

#: Enum defining all HTTP verbs
HTTPVerb = Enum('HTTPVerb',
    ( 'DELETE', 'GET', 'HEAD' 'OPTIONS', 'PATCH', 'POST', 'PUT', ))

_RESOURCE_NAME_FMT = '{}Resource'
_RESOURCE_ATTRIBUTES = ('name', 'url', 'action', 'request_class')
_REQUEST_NAME_FMT = '{}Request'

class DynamicResponse(dict):
    """
    """
    # Recipe for allowing . attribute access on a dictionary from
    # http://stackoverflow.com/questions/4984647/accessing-dict-keys-like-an-attribute-in-python
    def __init__(self, *args, **kwargs):
        super(DynamicResponse, self).__init__(*args, **kwargs)
        self.__dict__ = self

class RestClient(object):
   """
   Class for convenience off of which we will dynamically create
   the rest client
   """
   pass


def create_request_class(name, args, defaults):
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
   newclass = namedtuple(_REQUEST_NAME_FMT.format(name), signature)

   default_values = []

   for arg, value in sorted(defaults.items(), key=lambda x: signature.index(x[0])):
       try:
           index = signature.index(arg)
       except ValueError:
           raise RuntimeError('Not able to find argument: {}'.format(arg))

       default_values.append(value)

   newclass.__new__.__defaults__ = tuple(default_values)
   return newclass

def create_api_definition(api, defn, baseurl):
   defaults = dict([(k, v['default']) for k,v in defn['args'].items()
       if v is not None
       and isinstance(v, dict)
       and v.get('default', _NULL_OBJECT) is not _NULL_OBJECT])

   request = create_request_class(api, defn['args'].keys(), defaults)
   newclass = namedtuple(_RESOURCE_NAME_FMT.format(api), _RESOURCE_ATTRIBUTES)

   return newclass(api, baseurl + defn['url'], defn['action'], request)


def create_api_call_func(api):
   """
   From an api definition object create the related api call method
   that will validate the arguments for the api call and then
   dynamicaly dispatch the request to the appropriate requests module
   convenience method for the specific HTTP verb .
   """

   # Scopes some local context in which we can build
   # request functions with reflection that primed with
   # some static parameters.
   def api_call_func(self, **kwargs):

      try:
         action_name = api.action.upper()
         verb = HTTPVerb[action_name]
      except KeyError:
         raise RuntimeError('{} is not a valid http verb'.format(api.action))

      request = api.request_class(**kwargs)
      params = dict([ (k,v) for k,v in zip(request._fields, request) if v is not None ])

      if HTTPVerb.GET == verb:
         raw_response = requests.get(api.url, params=params, **self.reqargs)

      elif HTTPVerb.POST == verb:
         raw_response = requests.post(api.url, data=params, **self.reqargs)

      else:
         raise RuntimeError('{} is not a handled http verb'.format(verb))

      if raw_response.status_code != 200:
         raw_response.raise_for_status()

      # The object hook will convert all dictionaries from the json
      # objects in the response to a . attribute access
      response = raw_response.json(object_hook=lambda obj: DynamicResponse(obj))
      return response

   method_name = api.action.lower() + api.name.title()

   api_call_func.__name__ = method_name
   api_call_func.__doc__ = "{}\nParameters:\n  {}".format(
      method_name, '\n  '.join(api.request_class._fields))

   return api_call_func


def create_rest_client(name, apis, BaseClass=RestClient):
    """
    Generate the api call functions and attach them to the generated
    RestClient subclass with the name <Service>Client.
    """

    api_funcs = [create_api_call_func(api) for api in apis]
    api_mapper = dict([ (f.__name__, f) for f in api_funcs ])

    # Adapted from :
    # http://stackoverflow.com/questions/15247075/how-can-i-dynamically-create-derived-classes-from-a-base-class
    def __init__(self, **reqargs):
        BaseClass.__init__(self)
        setattr(self, 'reqargs', reqargs)

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

   ClientClass = create_rest_client(service_name, apis)

   setattr(service_module, 'resources', apis)
   setattr(service_module, 'Client', ClientClass)

   sys.modules[service_name.lower()] = service_module
   return service_module


def load_service(config_path):
   """
   Load a restful service specified by some YAML file at config_path.

   :param config_path: A pathlib Path object that points to the yaml
       config
   :returns: A python module containing a Client class, call factory,
       and the definition of each of the APIs defined by the config.
   """
   service_config = load_config(config_path)

   apis = []
   for api, defn in service_config['apis'].items():
       api_def= create_api_definition(api, defn, service_config['base_url'])
       apis.append(api_def)

   service_module = create_service_module(service_config['name'], apis)
   return service_module


def load_config(path):
   """
   Loads a yaml configuration.

   :param path: a pathlib Path object pointing to the configuration
   """
   with path.open('rb') as fi:
       file_bytes = fi.read()
       config = yaml.load(file_bytes.decode('utf-8'))

   return config


def parse_args():
   parser = argparse.ArgumentParser("gen rest")
   parser.add_argument('--config', '-c', required=True)
   parser.add_argument('--cert')
   parser.add_argument('--no-verify', action='store_false', dest='verify')
   parser.add_argument('--key')

   return parser.parse_args()


def main():
   args = parse_args()
   config_path = Path(args.config)
   service_module = load_service(config_path)

   print(service_module)
   print(dir(service_module))
   print(dir(service_module.Client))

   cert = args.cert
   verify = args.verify
   key = args.key

   client = service_module.Client(cert=cert, verify=verify)
   result = client.getPlaces(key=key, location='47.6097,-122.3331', keyword='bar', radius=10000)

   import random
   r1 = random.choice(result.results)
   print(r1.get('name'))
   details = client.getDetails(key=key, placeid=r1.place_id)
   print(details.keys())
   print(details.result.keys())
   print(details.result.opening_hours)

   # print(r1)
   # print(r1.rating)
   # print(dir(r1))
   # print(r1.geometry.location.lat)



if __name__ == '__main__':
   main()
