# -*- coding: utf-8 -*-
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

def load_config(path):
   with path.open('rb') as fi:
       file_bytes = fi.read()
       config = yaml.load(file_bytes.decode('utf-8'))

   return config

def create_request_class(name, args, defaults):
   signature = deque()

   # Modify the parameters of the signature such that those
   # with defaults follow those without
   for arg in args:
       if arg in defaults.keys():
           signature.append(arg)
       else:
           signature.appendleft(arg)

   signature = tuple(signature)
   newclass = namedtuple('{}Request'.format(name), signature)

   default_values = []

   for arg, value in sorted(defaults.items(), key=lambda x: signature.index(x[0])):
       try:
           index = signature.index(arg)
       except ValueError:
           raise RuntimeError('Not able to find argument: {}'.format(arg))

       default_values.append(value)

   newclass.__new__.__defaults__ = tuple(default_values)
   return newclass

# def create_response_class(name, args):
#    newclass = namedtuple('{}Response'.format(name), args)
#    newclass.__new__.__defaults__ = tuple([None] * len(args))

#    return newclass

def create_api_definition(api, defn, baseurl):
   defaults = dict([(k, v['default']) for k,v in defn['args'].items()
       if v is not None and isinstance(v, dict) and v.get('default', _NULL_OBJECT) is not _NULL_OBJECT])

   request = create_request_class(api, defn['args'].keys(), defaults)
#   response = create_response_class(api, defn['returns'])
   newclass = namedtuple('{}Resource'.format(api), ('name', 'url', 'action', 'request_class'))
   return newclass(api, baseurl + defn['url'], defn['action'], request)

def create_service_module(service_name, apis):
   service_module = imp.new_module(service_name.lower())

   for api in apis:
      setattr(service_module, api.name, api)

   setattr(service_module, 'apis', apis)

   sys.modules[service_name.lower()] = service_module
   return service_module

class BaseResponse(dict):
    def __init__(self, *args, **kwargs):
        super(BaseResponse, self).__init__(*args, **kwargs)
        self.__dict__ = self

HTTPVerb = Enum('HttpVerb',
    ('POST', 'PUT', 'PATCH', 'DELETE', 'GET', 'OPTIONS', 'HEAD'))


class RestClient(object):
   """
   """

   def __init__(self, apis, **reqargs):

       self.request_by_name = dict([ (a.name, a) for a in apis])
       self.reqargs = reqargs
       print(self.reqargs)

       for api in apis:

           method_name = api.action.lower() + api.name.title()

           def create_new_api_call_func(api_defn):
               # Scopes some local context in which we can build
               # request functions with reflection that primed with
               # some static parameters.
               def api_call_func(self, **kwargs):

                   try:
                       action_name = api_defn.action.upper()
                       verb = HTTPVerb[action_name]
                   except KeyError:
                       raise RuntimeError('{} is not a valid http verb'.format(api_defn.action))

                   if verb == HTTPVerb.GET:
                       request = api_defn.request_class(**kwargs)
                       params = dict([ (k,v) for k,v in zip(request._fields, request) if v is not None ])
                       params['_expand'] = 'instance,environments'
                       raw_response = requests.get(api.url, params=params, **self.reqargs)
                   else:
                       raise RuntimeError('{} is not a handled http verb'.format(verb))

                   if raw_response.status_code != 200:
                       raw_response.raise_for_status()

                   response = raw_response.json(object_hook=lambda obj: BaseResponse(obj))
                   return response

               api_call_func.__doc__ = "{}\nParameters:\n  {}".format(
                   method_name, '\n  '.join(api_defn.request_class._fields))

               return api_call_func

           client_func = create_new_api_call_func(api)
           client_func.__name__ = method_name
           setattr(self, method_name, types.MethodType(client_func, self))

def load_service(config_path):
   service_config = load_config(config_path)

   apis = []
   for api, defn in service_config['apis'].items():
       api_def= create_api_definition(api, defn, service_config['base_url'])
       apis.append(api_def)

   service_module = create_service_module(service_config['name'], apis)
   return service_module

def parse_args():
   parser = argparse.ArgumentParser("gen rest")
   parser.add_argument('--config', '-c', required=True)
   parser.add_argument('--cert')
   parser.add_argument('--no-verify', action='store_false', dest='verify')

   return parser.parse_args()

def main():


   args = parse_args()
   config_path = Path(args.config)
   service_module = load_service(config_path)

   print(service_module)
   print(dir(service_module))

   cert = args.cert
   verify = args.verify

   client = RestClient(service_module.apis, cert=cert, verify=verify)

   #print(service_module.Places)
   #print(dir(client))
   #result = client.getPlaces(key='XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', location='47.6097,-122.3331', radius=10000)
   #import random
   #r1 = random.choice(result.results)
   # print(r1.get('name'))
   # print(r1)
   # print(r1.rating)
   # print(dir(r1))
   # print(r1.geometry.location.lat)



if __name__ == '__main__':
   main()
