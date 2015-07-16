# -*- coding: UTF-8 -*-

import scarlett

import pygst
pygst.require('0.10')
import gobject
gobject.threads_init()
from dbus.mainloop.glib import DBusGMainLoop
dbus_loop = DBusGMainLoop(set_as_default=True)
# dsession = SessionBus(mainloop=dbus_loop)
dbus.mainloop.glib.threads_init()
import gst
import os
import threading
import time
import logging
from transitions import Machine
import dbus
import dbus.service

from scarlett.events import scarlett_event

from colorama import init, Fore, Back, Style

from scarlett.constants import (EVENT_SCARLETT_START,
                                EVENT_SCARLETT_STOP,
                                EVENT_STATE_CHANGED,
                                EVENT_TIME_CHANGED,
                                EVENT_CALL_SERVICE,
                                EVENT_SERVICE_EXECUTED,
                                EVENT_SERVICE_REGISTER,
                                EVENT_PLATFORM_DISCOVERED,
                                EVENT_SCARLETT_SAY,
                                EVENT_BRAIN_UPDATE,
                                EVENT_BRAIN_CHECK
                                )

SCARLETT_ROLE = 'listener'
CORE_OBJECT = 'GstlistenerFSM'

_INSTANCE = None

logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-9s) %(message)s',)


def setup_core(ss):
    logging.info("attempting to setup GstlistenerFSM")
    global _INSTANCE
    if _INSTANCE == None:
        _INSTANCE = GstlistenerFSM()
    return _INSTANCE


class GstlistenerFSM(gobject.GObject):
    __gproperties__ = {
        'override_parse': (
            gobject.TYPE_STRING,  # type
            'Override parse',  # nick name
            # description
            'Allows you to override what the gst parse line looks like',
            '',  # default value
            gobject.PARAM_READWRITE
        ),
        'failed': (
            gobject.TYPE_INT,  # type
            'Failed',  # nick name
            'Number of times recognition failed',  # description
            0,  # default value
            gobject.PARAM_READWRITE
        ),
        'kw_found': (
            gobject.TYPE_BOOLEAN,  # type
            'Service Keyword Match',  # nick name
            'Boolean value for keyword',  # description
            False,  # default value
            gobject.PARAM_READWRITE
        ),
        'now_time': (
            gobject.TYPE_STRING,  # type
            'Current Time',  # nick name
            'Value of current time',  # description
            None,  # default value
            gobject.PARAM_READWRITE
        )
    }

    __gsignals__ = {
        'gst-started': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
        'kw-found-ps': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
        'failed-ps': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,))
    }

    capability = []

    states = ['initalize', 'ready', 'running',
              'is_checking_states', 'time_change', 'done_checking_states']

    DBUS_NAME = 'org.scarlettapp.scarlettdaemon'
    DBUS_PATH = '/org/scarlettapp/scarlettdaemon'

  def __init__(self, *args, **kwargs):
    gobject.GObject.__init__(self)

    self.wit_thread = None
    self.loop = None

    self.failed = 0
    self.keyword_identified = 0
    self.config = scarlett.config
    self.override_parse = override_parse

    self.name = scarlett.brain.GstlistenerFSM.SCARLETT_ROLE

    # Initalize the state machine
    self.machine = Machine(model=self, states=scarlett.brain.GstlistenerFSM.GstlistenerFSM.states, initial='initalize')

    # startup transition
    self.machine.add_transition(trigger='startup', source='initalize', dest='ready')

    # checking_states transition
    self.machine.add_transition(trigger='checking_states', source='ready', dest='is_checking_states', conditions=['is_ready'])

    # array / dict of state machines connected to scarlett
    self._machines = {}

    # Check interval, in seconds
    self.interval = 1

    bus = dbus.SessionBus()
    self.remote = bus.get_object(GstlistenerFSM.DBUS_NAME, GstlistenerFSM.DBUS_PATH)

    # "/usr/local/share/pocketsphinx/model/hmm/en_US/hub4wsj_sc_8k"
    self.ps_hmm = self.get_hmm_full_path()
    self.ps_dict = self.get_dict_full_path()
    self.ps_lm = self.get_lm_full_path()
    self.ps_device = self.config.get('audio', 'usb_input_device')

    self.speech_system = self.config.get('speech', 'system')

    # default, use what we have set
    self.parse_launch_array = self._get_pocketsphinx_definition(
        override_parse)

    scarlett.log.debug(
        Fore.YELLOW +
        'Initializing gst-parse-launch -------->')
    self.pipeline = gst.parse_launch(
        ' ! '.join(self.parse_launch_array))

    listener = self.pipeline.get_by_name('listener')
    listener.connect('result', self.__result__)
    listener.set_property('configured', True)
    scarlett.log.debug(
        Fore.YELLOW +
        "Initializing connection to vader element -------->")
    # TODO: Play with vader object some more
    # vader = self.pipeline.get_by_name("vader")
    # vader.connect("vader-start", self._on_vader_start)
    # vader.connect("vader-stop", self._on_vader_stop)

    scarlett.log.debug(Fore.YELLOW + "Initializing Bus -------->")
    bus = self.pipeline.get_bus()
    bus.add_signal_watch()
    scarlett.log.debug(Fore.YELLOW + "Sending Message to Bus ---------->")
    bus.connect('message::application', self.__application_message__)

    logging.debug('running with %s and %s', args, kwargs)

    ss_listener = threading.Thread(target=self.start_listener)
    ss_listener.start()

  # GObject translates all the underscore characters to hyphen
  # characters so if you have a property called background_color,
  # its internal and valid name will be background-color.
  def do_get_property(self, property):
      if property.name == 'kw-match':
          return self.kw_match
      elif property.name == 'svc-kw-match':
          return self.svc_kw_match
      elif property.name == 'time-state':
          return self.time_state
      elif property.name == 'now-time':
          return self.now_time
      elif property.name == 'now-date':
          return self.now_date
      elif property.name == 'name':
          return self.name
      elif property.name == 'state':
          return self.state
      elif property.name == 'state-attribute':
          return self.state_attributes
      else:
          raise AttributeError, 'unknown property %s' % property.name

  def do_set_property(self, property, value):
       if property == 'kw-match':
           self.kw_match = value
       elif property == 'svc-kw-match':
           self.svc_kw_match = value
       elif property == 'time-state':
           self.time_state = value
       elif property == 'now-time':
           self.now_time = value
       elif property == 'now-date':
           self.now_date = value
       elif property == 'name':
           self.name = value
       elif property == 'state':
           self.state = value
       elif property == 'state-attributes':
           self.state_attributes = value
       else:
           raise AttributeError, 'unknown property %s' % property

  def start_listener(self):
      logging.debug('running with %s and %s', self.args, self.kwargs)

      # register service start
      listener_connect = scarlett_event('service_state',
        data=CORE_OBJECT
       )
      self.emit('listener-started', listener_connect)

      logging.debug('Starting')

      self.pipeline.set_state(gst.STATE_PLAYING)

      scarlett.log.debug(Fore.YELLOW +
                         'KEYWORD: ' +
                         self.config.get('scarlett','owner'))

      self.loop = gobject.MainLoop()
      self.loop.run()

      logging.debug('Exiting')

    def stop(self):
        self.pipeline.set_state(gst.STATE_NULL)

        if self.loop is not None:
            self.loop.quit()

    def scarlett_start_listen(self):
        self.pipeline.set_state(gst.STATE_PLAYING)

    def scarlett_stop_listen(self):
        self.pipeline.set_state(gst.STATE_READY)

    def scarlett_pause_listen(self):
        self.pipeline.set_state(gst.STATE_PAUSED)

    def scarlett_reset_listen(self):
        self.failed = int(
            self.brain.set_brain_item_r(
                'scarlett_failed',
                0))
        self.keyword_identified = int(
            self.brain.set_brain_item_r(
                'm_keyword_match',
                0))

    def partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""
        pass

    def result(self, hyp, uttid):
        """Forward result signals on the bus to the main thread."""
        scarlett.log.debug(Fore.YELLOW + "Inside result function")
        if hyp in self.config.get('scarlett', 'keywords'):
            scarlett.log.debug(
                Fore.YELLOW +
                "HYP-IS-SOMETHING: " +
                hyp +
                "\n\n\n")
            scarlett.log.debug(
                Fore.YELLOW +
                "UTTID-IS-SOMETHING:" +
                uttid +
                "\n")
            self.failed = int(
                self.brain.set_brain_item_r(
                    'scarlett_failed',
                    0))
            # redis implementation # self.keyword_identified = 1
            self.keyword_identified = int(
                self.brain.set_brain_item_r(
                    'm_keyword_match',
                    1))
            scarlett.basics.voice.play_block('pi-listening')
        else:
            self.failed_temp = int(
                self.brain.get_brain_item('scarlett_failed')) + 1
            self.failed = int(
                self.brain.set_brain_item_r(
                    'scarlett_failed',
                    self.failed_temp))
            scarlett.log.debug(
                Fore.YELLOW +
                "self.failed = %i" %
                (self.failed))
            if self.failed > 4:
                # reset pipline
                self.scarlett_reset_listen()
                ScarlettTalk.speak(
                    " %s , if you need me, just say my name." %
                    (self.config.get('scarlett', 'owner')))

    def run_cmd(self, hyp, uttid):
        scarlett.log.debug(Fore.YELLOW + "Inside run_cmd function")
        scarlett.log.debug(Fore.YELLOW + "KEYWORD IDENTIFIED BABY")
        scarlett.log.debug(
            Fore.RED +
            "self.keyword_identified = %i" %
            (self.keyword_identified))
        if hyp == 'CANCEL':
            self.cancel_listening()
        else:
            self.commander.check_cmd(hyp)
            self.keyword_identified = int(
                self.brain.get_brain_item('m_keyword_match'))
            scarlett.log.debug(
                Fore.RED +
                "AFTER run_cmd, self.keyword_identified = %i" %
                (self.keyword_identified))

    def listen(self, valve, vader):
        scarlett.log.debug(Fore.YELLOW + "Inside listen function")
        scarlett.basics.voice.play_block('pi-listening')
        valve.set_property('drop', False)
        valve.set_property('drop', True)

    def cancel_listening(self):
        scarlett.log.debug(Fore.YELLOW + "Inside cancel_listening function")
        self.scarlett_reset_listen()
        scarlett.log.debug(Fore.YELLOW + "self.failed = %i" % (self.failed))
        scarlett.log.debug(
            Fore.RED +
            "self.keyword_identified = %i" %
            (self.keyword_identified))

    def get_hmm_full_path(self):
        if os.environ.get('SCARLETT_HMM'):
            _hmm_full_path = os.environ.get('SCARLETT_HMM')
        else:
            _hmm_full_path = self.config.get('pocketsphinx', 'hmm')

        return _hmm_full_path

    def get_lm_full_path(self):
        if os.environ.get('SCARLETT_LM'):
            _lm_full_path = os.environ.get('SCARLETT_LM')
        else:
            _lm_full_path = self.config.get('pocketsphinx', 'lm')

        return _lm_full_path

    def get_dict_full_path(self):
        if os.environ.get('SCARLETT_DICT'):
            _dict_full_path = os.environ.get('SCARLETT_DICT')
        else:
            _dict_full_path = self.config.get('pocketsphinx', 'dict')

        return _dict_full_path

    def get_pipeline(self):
        scarlett.log.debug(Fore.YELLOW + "Inside get_pipeline")
        return self.pipeline

    def get_voice(self):
        scarlett.log.debug(Fore.YELLOW + "Inside get_voice")
        return self.voice

    def get_pipeline_state(self):
        return self.pipeline.get_state()

    def _get_pocketsphinx_definition(self, override_parse):
        scarlett.log.debug(Fore.YELLOW + "Inside _get_pocketsphinx_definition")
        """Return ``pocketsphinx`` definition for :func:`gst.parse_launch`."""
        # default, use what we have set
        if not override_parse:
            return [
                'alsasrc device=' +
                self.ps_device,
                'queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                'audioconvert',
                'audioresample',
                'audio/x-raw-int, rate=16000, width=16, depth=16, channels=1',
                'audioresample',
                'audio/x-raw-int, rate=8000',
                'vader name=vader auto-threshold=true',
                'pocketsphinx lm=' +
                self.ps_lm +
                ' dict=' +
                self.ps_dict +
                ' hmm=' +
                self.ps_hmm +
                ' name=listener',
                'fakesink dump=1']
            # NOTE, I commented out the refrence to the tee
            # 'fakesink dump=1 t.'
        else:
            return override_parse

    def _get_vader_definition(self):
        scarlett.log.debug(Fore.YELLOW + "Inside _get_vader_definition")
        """Return ``vader`` definition for :func:`gst.parse_launch`."""
        # source: https://github.com/bossjones/eshayari/blob/master/eshayari/application.py
        # Convert noise level from spin button range [0,32768] to gstreamer
        # element's range [0,1]. Likewise, convert silence from spin button's
        # milliseconds to gstreamer element's nanoseconds.

        # MY DEFAULT VADER DEFINITON WAS: vader name=vader auto-threshold=true
        # vader name=vader auto-threshold=true
        noise = 256 / 32768
        silence = 300 * 1000000
        return ("vader "
                + "name=vader "
                + "auto-threshold=false "
                + "threshold=%.9f " % noise
                + "run-length=%d " % silence
                )

    def _on_vader_start(self, vader, pos):
        scarlett.log.debug(Fore.YELLOW + "Inside _on_vader_start")
        """Send start position as a message on the bus."""
        import gst
        struct = gst.Structure("start")
        pos = pos / 1000000000  # ns to s
        struct.set_value("start", pos)
        vader.post_message(gst.message_new_application(vader, struct))

    def _on_vader_stop(self, vader, pos):
        scarlett.log.debug(Fore.YELLOW + "Inside _on_vader_stop")
        """Send stop position as a message on the bus."""
        import gst
        struct = gst.Structure("stop")
        pos = pos / 1000000000  # ns to s
        struct.set_value("stop", pos)

    def __result__(self, listener, text, uttid):
        """We're inside __result__"""
        scarlett.log.debug(Fore.YELLOW + "Inside __result__")
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __partial_result__(self, listner, text, uttid):
        """We're inside __partial_result__"""
        scarlett.log.debug(Fore.YELLOW + "Inside __partial_result__")
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __run_cmd__(self, listener, text, uttid):
        """We're inside __run_cmd__"""
        scarlett.log.debug(Fore.YELLOW + "Inside __run_cmd__")
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __application_message__(self, bus, msg):
        msgtype = msg.structure.get_name()
        scarlett.log.debug(Fore.YELLOW + "msgtype: " + msgtype)
        if msgtype == 'partial_result':
            self.partial_result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'result':
            if self.keyword_identified == 1:
                self.run_cmd(msg.structure['hyp'], msg.structure['uttid'])
            else:
                self.result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'run_cmd':
            self.run_cmd(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == gst.MESSAGE_EOS:
            pass
            # DISABLE # TODO: SEE IF WE NEED THIS # self.pipeline.set_state(gst.STATE_NULL)
        elif msgtype == gst.MESSAGE_ERROR:
            (err, debug) = msgtype.parse_error()
            scarlett.log.debug(Fore.RED + "Error: %s" % err, debug)
            pass
            # DISABLE # TODO: SEE IF WE NEED THIS # self.pipeline.set_state(gst.STATE_NULL)
            # DISABLE # TODO: SEE IF WE NEED THIS # (err, debug) = msgtype.parse_error()
            # DISABLE # TODO: SEE IF WE NEED THIS # scarlett.log.debug(Fore.RED + "Error: %s" % err, debug)



# Register to be able to emit signals
gobject.type_register(GstlistenerFSM)
