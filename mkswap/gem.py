import rel, random
from rel.util import ask, listen
from .backend import spew, die, dpost
from .base import Worker

class Req(Worker):
	def __init__(self, path, gem, params={}, cb=spew, client_order_id=None):
		self.cb = cb
		self.gem = gem
		self.path = path
		self.attempt = 0
		self.params = params
		self.noretry = False
		self.client_order_id = client_order_id
		self.name = path.split("/").pop()
		if client_order_id:
			self.name = "%s %s"%(self.name, client_order_id)
		if "order_id" in params:
			self.name = "%s %s"%(self.name, params["order_id"])
		self.log(params)
		self.gem.reg(self)

	def sig(self):
		return "Req[%s]"%(self.name,)

	def get(self):
		self.attempt += 1
		self.log("get(%s)"%(self.attempt,))
		dpost(self.path, ask("credHead", self.path, self.params), self.receive, self.retry)

	def resubmit(self):
		self.log("resubmit(%s)"%(self.attempt,),
			self.noretry and "aborting retry!" or "passing self to gem")
		self.noretry or self.gem.add(self, True)

	def retry(self, reason, timeout=None):
		timeout = timeout or random.randint(2, 10)
		self.log("retry(%s)[%s] %s seconds!"%(self.attempt, reason, timeout))
		rel.timeout(timeout, self.resubmit)

	def receive(self, res):
		if "result" not in res or res["result"] != "error":
			self.gem.unreg(self)
			return (self.cb or self.log)(res)
		reason = res["reason"]
		message = res["message"]
		self.log("receive(%s) %s error: %s"%(self.attempt, reason, message))
		if reason not in ["RateLimit", "RateLimited", "InvalidNonce"]:
			return die(reason, res)
		if reason == "RateLimit":
			self.gem.pause()
		self.warn(reason)
		self.retry(reason, reason == "RateLimited" and int(message.split(" ")[-2]) / 1000)

class Gem(Worker):
	def __init__(self):
		self.reqs = {}
		self.counts = {
			"pauses": 0,
			"trades": 0,
			"cancels": 0,
			"retries": 0,
			"requests": 0
		}
		self.pending = []
		self.paused = False
		self.pauser = rel.timeout(None, self.unpause)
		rel.timeout(0.11, self.churn) # 90% of rate limit
		listen("preventRetry", self.preventRetry)

	def status(self):
		return {
			**self.counts,
			"paused": self.paused,
			"pending": len(self.pending),
			"active": len(self.reqs.keys())
		}

	def inc(self, count):
		self.counts[count] += 1

	def preventRetry(self, rname):
		self.reqs[rname].noretry = True

	def reg(self, req):
		self.reqs[req.name] = req

	def unreg(self, req):
		req.gem = None
		del self.reqs[req.name]

	def churn(self):
		if self.pending and not self.paused:
			self.inc("requests")
			self.pending.pop(0).get()
		return True

	def pause(self):
		self.inc("pauses")
		self.log("pausing for 5 seconds!!")
		self.pauser.pending() and self.pauser.delete()
		self.pauser.add(5)
		self.paused = True

	def unpause(self):
		self.log("unpausing!")
		self.paused = False

	def add(self, req, retry=False):
		self.pending.append(req)
		retry and self.inc("retries")
		self.log("added to", len(self.pending), "long queue:",
			req.name, "attempt:", req.attempt, "paused:", self.paused)

	def get(self, path, cb=None, params={}, client_order_id=None):
		self.log("get(%s)"%(path,), client_order_id, params)
		self.add(Req(path, self, params, cb, client_order_id))

	def accounts(self, network, cb=None):
		self.get("/v1/addresses/%s"%(network,), cb)

	def balances(self, cb=None):
		self.get("/v1/balances", cb)

	def trade(self, trade, cb=None):
		self.inc("trades")
		self.get("/v1/order/new", cb, trade, trade["client_order_id"])

	def cancel(self, trade, cb=None):
		self.inc("cancels")
		self.get("/v1/order/cancel", cb, {
			"order_id": trade["order_id"]
		}, trade["client_order_id"])

	def withdraw(self, symbol, amount, address, memo, cb=None):
		self.get("/v1/withdraw/%s"%(symbol,), cb, {
			"memo": memo,
			"address": address,
			"amount": str(amount)
		})

gem = Gem()