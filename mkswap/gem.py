import rel, random
from .backend import ask, spew, die, dpost
from .base import Worker

class Req(Worker):
	def __init__(self, path, gem, params={}, cb=spew):
		self.cb = cb
		self.gem = gem
		self.path = path
		self.attempt = 0
		self.params = params
		self.log(path, params)

	def get(self):
		self.attempt += 1
		self.log("get(%s, %s)"%(self.path, self.attempt))
		dpost(self.path, ask("credHead", self.path, self.params), self.receive, self.retry)

	def resubmit(self):
		self.log("resubmit(%s) passing self back to gem - attempt %s"%(self.path, self.attempt))
		self.gem.add(self)

	def retry(self, reason, timeout=None):
		timeout = timeout or random.randint(5, 20)
		self.log("retry(%s #%s)[%s] %s seconds!"%(self.path, self.attempt, reason, timeout))
		rel.timeout(timeout, self.resubmit)

	def decommission(self):
		self.gem = None

	def receive(self, res):
		if "result" not in res or res["result"] != "error":
			self.decommission()
			return (self.cb or self.log)(res)
		reason = res["reason"]
		message = res["message"]
		self.log("receive(%s) %s error: %s"%(self.path, reason, message))
		if reason not in ["RateLimit", "RateLimited", "InvalidNonce"]:
			return die(reason, res)
		if reason == "RateLimit":
			self.gem.pause()
		self.warn(reason)
		self.retry(reason, reason == "RateLimited" and int(message.split(" ")[-2]) / 1000)

class Gem(Worker):
	def __init__(self):
		self.pending = []
		self.paused = False
		self.pauser = rel.timeout(None, self.unpause)
		rel.timeout(0.2, self.churn) # 1/2 of rate limit

	def churn(self):
		self.pending and not self.paused and self.pending.pop(0).get()
		return True

	def pause(self):
		self.log("pausing for 5 seconds!!")
		self.pauser.pending() and self.pauser.delete()
		self.pauser.add(5)
		self.paused = True

	def unpause(self):
		self.log("unpausing!")
		self.paused = False

	def add(self, req):
		self.pending.append(req)
		self.log("added to", len(self.pending), "long queue:", req.path, req.attempt)

	def get(self, path, cb=None, params={}):
		self.log("get(%s)"%(path,), params)
		self.add(Req(path, self, params, cb))

	def accounts(self, network, cb=None):
		self.get("/v1/addresses/%s"%(network,), cb)

	def balances(self, cb=None):
		self.get("/v1/balances", cb)

	def trade(self, trade, cb=None):
		self.get("/v1/order/new", cb, trade)

	def cancel(self, trade, cb=None):
		self.get("/v1/order/cancel", cb, { "order_id": trade["order_id"] })

	def withdraw(self, symbol, amount, address, memo, cb=None):
		self.get("/v1/withdraw/%s"%(symbol,), cb, {
			"memo": memo,
			"address": address,
			"amount": str(amount)
		})

gem = Gem()