import rel, json, websocket
from rel import start, stop
from rel.util import log, read, write, remember, recall, memget, emit, ask, listen

predefs = {
	"strategy": "rsi",
	"platform": "gemini",
	"balances": {
		"USD": 100,
		"ETH": 0.05,
		"BTC": 0.0025
	}
}
presets = [{
	"strategy": "slosh",
	"globalTrade": True,
	"globalStrategy": True,
	"symbols": ["BTCUSD", "ETHUSD"]
}, {
	"symbols": ["ETHUSD"]
}, {
	"symbols": ["BTCUSD"]
}, {
	"symbols": ["BTCUSD", "ETHUSD", "ETHBTC"]
}, {
	"platform": "dydx",
	"strategy": "slosh",
	"globalTrade": True,
	"globalStrategy": True,
	"symbols": ["BTC-USD", "ETH-USD"]
}, {
	"platform": "dydx",
	"symbols": ["ETH-USD"]
}, {
	"platform": "dydx",
	"symbols": ["BTC-USD"]
}]

def spew(event):
	if hasattr(event, "decode"):
		event = event.decode()
	log(json.dumps(event))

def gemget(path, cb, params={}):
	from dez.http import post
	post(hosts["gemini"], path, port=443, secure=True, headers=ask("credHead", path, params),
		cb=cb, timeout=10, json=True)

def gemtrade(trade, cb=spew):
	gemget("/v1/order/new", cb, trade)

def crsub(streamname):
	return {
		"name": "SubscribeTicker",
		"data": streamname
	}

def ddtrades(streamname):
	return {
		"type": "subscribe",
		"channel": "v3_trades",
		"id": streamname
	}

def ddorders(streamname):
	return {
		"type": "subscribe",
		"channel": "v3_orderbook",
		"id": streamname
	}

def ddaccount(ts):
	creds = ask("apiCreds")
	spew(creds)
	return {
		"id": ask("id"),
		"timestamp": ts,
		"accountNumber": 0,
		"type": "subscribe",
		"apiKey": creds["key"],
		"channel": "v3_accounts",
		"passphrase": creds["passphrase"],
		"signature": ask("signature", "/ws/accounts", ts)
	}

def subber(streamname, submaker, doafter=None):
	def _subber(ws):
		log("opened - sending sub block")
		ws.jsend(submaker(streamname))
		doafter and doafter()
	return _subber

def jsend(ws):
	def _jsend(jmsg):
		msg = json.dumps(jmsg)
		log("sending:", msg)
		ws.send(msg)
	return _jsend

STAGING = True
hosts = {
	"gemini": "api.gemini.com",
	"dydx": "api.dydx.exchange"
}
platforms = { # setStaging() sets dacc/dydx/gemorders feeds, gemini feeder
	"dacc": {
		"subber": ddaccount,
		"credHead": "/ws/accounts"
	},
	"dydx": {
		"subber": ddtrades # or ddorders
	},
	"chainrift": {
		"feed": "wss://ws.chainrift.com/v1",
		"subber": crsub
	},
	"gemini": {},
	"gemorders": {
		"credHead": "/v1/order/events"
	}
}

def setStaging(stagflag=STAGING):
	log("setStaging(%s)"%(stagflag,))
	global STAGING
	h = hosts
	p = platforms
	STAGING = stagflag
	h["dydx"] = "api.dydx.exchange"
	h["gemini"] = "api.gemini.com"
	if STAGING:
		h["dydx"] = h["dydx"].replace("api.", "api.stage.")
		h["gemini"] = h["gemini"].replace("api.", "api.sandbox.")
	p["dacc"]["feed"] = p["dydx"]["feed"] = "wss://%s/v3/ws"%(h["dydx"],)
	p["gemini"]["feeder"] = lambda sname : "wss://%s/v1/marketdata/%s"%(h["gemini"], sname)
	p["gemorders"]["feed"] = "wss://%s/v1/order/events"%(h["gemini"],)

setStaging()

def feed(platname, streamname=None, **cbs): # {on_message,on_error,on_open,on_close}
	plat = platforms[platname]
	feed = "feed" in plat and plat["feed"] or plat["feeder"](streamname)
	if "subber" in plat:
		cbs["on_open"] = subber(streamname,
			plat["subber"], getattr(cbs, "on_open", None))
	if "credHead" in plat:
		cbs["header"] = ask("credHead", plat["credHead"])
	ws = websocket.WebSocketApp(feed, **cbs)
	ws.jsend = jsend(ws)
	ws.run_forever(dispatcher=rel, reconnect=1)
	return ws

def echofeed(platform="gemini", streamname="ETHBTC"):
	return feed(platform, streamname,
		on_message = lambda ws, msg : log(msg),
		on_close = lambda ws, code, msg: log("close!", code, msg),
		on_error = lambda ws, exc : log("error!", str(exc)))

def dydxtest():
	echofeed("dydx", "BTC-USD")
	start()

edata = {
	"lastReason": None
}

def events(message, use_initial=False):
	msg = json.loads(message)
	if "events" in msg: # gemini
		ez = []
		for event in msg["events"]:
			reason = event.get("reason")
			goodinit = reason == "initial" and use_initial
			if reason != "place" and not goodinit:
				if reason == edata["lastReason"]:
					print(".", end="")
				else:
					print("\nskipping reason:", reason, end="")
					edata["lastReason"] = reason
			else:
				if not event.get("side"):
					log("using makerSide")
					event["side"] = event.get("makerSide")
				if not event.get("side"):
					log("skipping sideless", event)
				elif event.get("type") == "change":
					ez.append(event)
				else:
					log("skipping", event)
		return ez
	else: # dydx
		log("\n\n\n", message, "\n\n\n")
		if "contents" in msg:
			return msg["contents"]["trades"]
		else:
			log("skipping event!!!")
			return []