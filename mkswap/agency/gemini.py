import base64, json, time, hmac, hashlib
from ..base import Worker
from ..backend import emit, listen, memget, gemget

LIVE = False

class Gemini(Worker):
	def __init__(self):
		self.apiKey = memget("gemini key")
		self.account = memget("gemini account")
		self.secret = memget("gemini secret").encode()
		self.actives = []
		self.backlog = []
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

	def submit(self, trade):
		self.actives.append(trade)
		gemget("/v1/order/new", self.log, trade)

	def enqueue(self, trade):
		self.backlog.append(trade)
		while self.backlog and len(self.actives) < 10:
			self.submit(self.backlog.pop(0))

	def trade(self, trade):
		self.log("TRADE:", trade)
		if not LIVE: return
		trade["type"] = "exchange limit"
		for item in ["price", "amount"]:
			trade[item] = str(trade[item])
		self.enqueue(trade)