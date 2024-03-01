import traceback, pprint
from websocket import WebSocketBadStatusException
from .backend import log, stop, feed, emit
from .config import config

class Worker(object):
	def sig(self):
		return self.__class__.__name__

	def log(self, *msg):
		line = "\n%s %s"%(self.sig(), " ".join([str(m) for m in msg]))
		if config.base.unspammed:
			if getattr(self, "_lastlog", None) == line:
				return print(".", end="", flush=True)
			self._lastlog = line
		log(line)

	def warn(self, msg, extra=None):
		self.log("WARNING:", msg)
		extra and self.log(extra)
		emit("warning", "%s: %s"%(self.sig(), msg), extra)

	def error(self, *msg):
		self.log("ERROR", *msg)
		traceback.print_exc()
		stop()

class Feeder(Worker):
	def feed(self, platform, channel=None):
		self.log("feed", platform, channel)
		if getattr(self, "ws", None):
			return self.log("feed already loaded!")
		self.ws = feed(platform, channel, on_open=self.on_open,
			on_reconnect=self.on_reconnect, on_message=self.on_message,
			on_error=self.on_error, on_close=self.on_close)

	def start_feed(self):
		self.feed(self.platform, getattr(self, "symbol", None))

	def on_error(self, ws, err):
		if type(err) is WebSocketBadStatusException:
			self.warn("handshake failed - retrying")
			self.ws = None
			self.start_feed()
		else:
			self.error(err)

	def on_message(self, ws, msg):
		self.log("message:")
		pprint.pprint(msg)

	def on_close(self, ws, code, message):
		self.warn("closed %s"%(code,), message)

	def on_open(self, ws):
		self.log("opened!!")

	def on_reconnect(self, ws):
		self.warn("reconnected")