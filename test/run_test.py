import argparse
import concurrent.futures

from pathlib import Path

from rekt import load_service
import requests.exceptions

def parse_args():
   parser = argparse.ArgumentParser("gen-rest")
   parser.add_argument('--config', '-c', required=True)
   parser.add_argument('--cert')
   parser.add_argument('--no-verify', action='store_false', dest='verify')
   parser.add_argument('--key')

   return parser.parse_args()

def main():
   # TODO: allow for different locations between args/body for each verb
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
   try:
      result = client.get_places(key=key, location='47.6097,-122.3331', keyword='bar', radius=10000)
      print(result.keys())
   except requests.exceptions.HTTPError as e:
      print(e)
      print(e.response.text)
      raise e

   my_place = result.results[0]
   f = client.async_get_details(key=key, placeid=my_place.place_id)
   print(f)
   f = next(concurrent.futures.as_completed([f]))
   print(f.result().keys())
   raise SystemExit()

   details = []
   futures = []
   for prediction in result.results:
       f = client.async_get_details(key=key, placeid=prediction.place_id)
       futures.append(f)

   for f in concurrent.futures.as_completed(futures):
       response = f.result()
       if response.status == 'INVALID_REQUEST':
          print(f)
          continue

       venue_types = set(response.result.types)
       if not any( ((vt in venue_types) for vt in ['restaurant', 'bar', 'coffee', 'food', 'cafe', 'pub']) ):
           continue

       details.append(response.result)

   import random
   details = random.choice(details)

   print(str(details.opening_hours).encode('utf-8'))
   print()
   print(details.vicinity)
   print()
   print(details.opening_hours)



   response = client.get_text_search(key=key, query='Bambin', location='47.6097,-122.3331', radius=10000)
   print(response.results)
   print()

   response = client.get_places_auto_complete(key=key, input='5 Point', location='47.6097,-122.3331', radius=2500, types='establishment')
   print(response)
   print()

   details = []
   futures = []
   for prediction in response.predictions:
       f = client.async_get_details(key=key, placeid=prediction.place_id)
       futures.append(f)

   for f in concurrent.futures.as_completed(futures):
       response = f.result()
       if response.status == 'INVALID_REQUEST':
           continue

       venue_types = set(response.result.types)
       if not any( ((vt in venue_types) for vt in ['restaurant', 'bar', 'coffee', 'food', 'cafe', 'pub']) ):
           continue

       details.append(response.result)

   from pprint import pformat
   print(pformat(details))


#   print('{}'.format(details).encode('utf-8').decode('ascii', errors='ignore'))

if __name__ == '__main__':
   main()
