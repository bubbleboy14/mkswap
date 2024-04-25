import json, traceback, rel
from websocket import WebSocketBadStatusException
from .backend import log, stop, feed, emit, wsdebug
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

MAX_WAIT = 16

class Feeder(Worker):
	def feed(self, platform, channel=None):
		self.log("feed", platform, channel)
		ws = getattr(self, "ws", None)
		if ws:
			if ws.has_done_teardown:
				ws.run_forever(dispatcher=rel, reconnect=1)
				return self.reset_wait("refreshing feed!")
			if not self.waited_enough():
				self.warn("feed already loaded!")
				return True
			self.reset_wait("recreating feed!")
			ws.close()
		self.ws = feed(platform, channel, on_open=self.on_open,
			on_reconnect=self.on_reconnect, on_message=self.on_message,
			on_error=self.on_error, on_close=self.on_close)

	def start_feed(self):
		self.feed(self.platform, getattr(self, "symbol", None))
		self.heartstart()

	def waited_enough(self):
		return self.get_wait(False) == MAX_WAIT

	def reset_wait(self, msg):
		self._wait = 1
		self.warn(msg)

	def get_wait(self, double=True):
		self._wait = getattr(self, "_wait", 1)
		if double and self._wait < MAX_WAIT:
			self._wait *= 2
		return self._wait

	def on_error(self, ws, err):
		self.setdebug(True)
		if type(err) is WebSocketBadStatusException:
#			self.ws = None
			wait = self.get_wait()
			rel.timeout(wait, self.start_feed)
			self.warn("handshake failed - retrying in %s seconds"%(wait,))
		else:
			self.error(err)

	def on_message(self, ws, msg):
		config.base.unspammed or self.log("message:", msg)
		data = json.loads(msg)
		if type(data) is dict and data.get("type") == "heartbeat":
			return self.heartbeat()
		self.heartstart()
		self.message(data)

	def heartstop(self):
		self.warn("heart stopped! restarting...")
		self.start_feed()

	def heartstart(self):
		if not config.feeder.heartbeat:
			return
		if not hasattr(self, "heart"):
			self.log("heart start")
			self.heart = rel.timeout(None, self.heartstop)
		self.heart.pending() and self.heart.delete()
		self.heart.add(config.feeder.heartbeat)

	def heartbeat(self):
		self.log("heartbeat")
		self.heartstart()

	def message(self, msg): # override!
		self.log(msg)

	def setdebug(self, ison):
		if config.feeder.wsdebug == "auto":
			wsdebug(ison)

	def on_close(self, ws, code, message):
		self.warn("closed %s"%(code,), message)
		self.setdebug(True)

	def on_open(self, ws):
		self.warn("opened!!")
		self.setdebug(False)
		self.on_ready()

	def on_reconnect(self, ws):
		self.warn("reconnected")
		self.setdebug(False)
		self.heartstart()
		self.on_ready()

	def on_ready(self):
		pass # override