# -*- coding: utf-8 -*-

from scarlett.core.config import Config, ScarlettConfigLocations
#### DISABLED UNTIL READY # import scarlett.plugin
import datetime
import os
import platform
import logging
import logging.config
import scarlett.errors

__author__  = 'Malcolm Jones'
__email__   = 'bossjones@theblacktonystark.com'
__version__ = '0.3.0'
Version = __version__  # for backware compatibility

# http://bugs.python.org/issue7980
datetime.datetime.strptime('', '')

UserAgent = 'Scarlett/%s Python/%s %s/%s' % (
    __version__,
    platform.python_version(),
    platform.system(),
    platform.release()
)

config = Config()


def init_logging():
    for file in ScarlettConfigLocations:
        try:
            logging.config.fileConfig(os.path.expanduser(file))
        except:
            pass


class NullHandler(logging.Handler):

    def emit(self, record):
        pass

log = logging.getLogger('scarlett')
perflog = logging.getLogger('scarlett.perf')
log.addHandler(NullHandler())
perflog.addHandler(NullHandler())
init_logging()

# convenience function to set logging to a particular file


def set_file_logger(name, filepath, level=logging.INFO, format_string=None):
    global log
    if not format_string:
        format_string = "%(asctime)s %(name)s [%(levelname)s]:%(message)s"
    logger = logging.getLogger(name)
    logger.setLevel(level)
    fh = logging.FileHandler(filepath)
    fh.setLevel(level)
    formatter = logging.Formatter(format_string)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    log = logger


def set_stream_logger(name, level=logging.DEBUG, format_string=None):
    global log
    if not format_string:
        format_string = "%(asctime)s %(name)s [%(levelname)s]:%(message)s"
    logger = logging.getLogger(name)
    logger.setLevel(level)
    fh = logging.StreamHandler()
    fh.setLevel(level)
    formatter = logging.Formatter(format_string)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    log = logger


# def connect_voice(brain, **kwargs):
#     global log
#     scarlett.log.debug("connect_voice")
#     from scarlett.basics.voice import Voice
#     return Voice(brain)


# def connect_forecastio(voice, brain, **kwargs):
#     global log
#     scarlett.log.debug("connect_forecastio")
#     from scarlett.features.forecast import FeatureForecast
#     return FeatureForecast(voice, brain)


# def connect_wordnik(voice, brain, **kwargs):
#     global log
#     scarlett.log.debug("connect_wordnik")


# def connect_nltk(voice, brain, **kwargs):
#     global log
#     scarlett.log.debug("connect_nltk")


# def connect_hue(voice, brain, **kwargs):
#     global log
#     scarlett.log.debug("connect_hue")
#     from scarlett.features.hue_lights import FeatureHueLights
#     return FeatureHueLights(voice, brain)


# def connect_time(voice, brain, **kwargs):
#     global log
#     scarlett.log.debug("connect_time")
#     from scarlett.features.time import FeatureTime
#     return FeatureTime(voice, brain)


# def connect_wa(voice, brain, **kwargs):
#     global log
#     scarlett.log.debug("connect_wa")


# def connect_brain():
#     global log
#     scarlett.log.debug("connect_brain")
#     from scarlett.brain import ScarlettBrain
#     return ScarlettBrain(brain_name="DeepThought", flush=True)
