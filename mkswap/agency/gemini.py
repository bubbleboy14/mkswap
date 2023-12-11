import base64, json, time, hmac, hashlib
from ..base import Worker
from ..backend import emit, listen, memget, gemget

LIVE = False

class Gemini(Worker):
	def __init__(self):
		self.apiKey = memget("gemini key")
		self.account = memget("gemini account")
		self.secret = memget("gemini secret").encode()
		listen("credHead", self.credHead)
		emit("clientReady")

	def credHead(self, path, params={}):
		payload = self.payload(path, params)
		return {
			"Content-Length": "0",
			"Cache-Control": "no-cache",
			"Content-Type": "text/plain",
			"X-GEMINI-APIKEY": self.apiKey,
			"X-GEMINI-PAYLOAD": payload.decode(),
			"X-GEMINI-SIGNATURE": self.signature(payload)
		}

	def payload(self, path, params={}):
		params.update({
			"request": path,
			"nonce": time.time(),
			"account": self.account
		})
		pl = json.dumps(params).encode()
		self.log("payload(%s)"%(path,), pl)
		return base64.b64encode(pl)

	def signature(self, payload):
		return hmac.new(self.secret, payload, hashlib.sha384).hexdigest()

	def trade(self, trade):
		self.log("TRADE:", trade)
		if not LIVE: return
		params = { "type": "exchange limit" }
		params.update(trade)
		gemget("/v1/order/new", self.log, params)