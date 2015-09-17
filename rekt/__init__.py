# -*- coding: utf-8 -*-
"""
rekt
====

rekt is a wrapper around the requests library that makes generic rest
operations less painful. I was frustrated with the implementation of
many service specific rest wrappers especially for google apis, this
library is meant to be generic and dynamic enough by templating the common
client code for most rest services.
"""
__version__ = '0.2015.9.16'
__all__ = ['load_service']

from rekt.service import load_service
