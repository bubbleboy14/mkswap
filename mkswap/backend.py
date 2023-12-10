import os, sys, rel, json, base64, websocket

def log(*msg):
	print(*msg)

def read(fname):
	if not os.path.exists(fname):
		return
	f = open(fname, 'r')
	data = f.read()
	f.close()
	return data and json.loads(base64.b64decode(data).decode())

def write(fname, data):
	f = open(fname, 'w')
	f.write(base64.b64encode(json.dumps(data).encode()).decode())
	f.close()

membank = {}
remembered = read(".membank")
remembered and membank.update(remembered)

def remember(key, data, ask=True):
	if ask and input("remember %s for next time? [Y/n] "%(key,)).lower().startswith("n"):
		return log("ok, not remembering", key)
	membank[key] = data
	write(".membank", membank)

def recall(key):
	return membank.get(key, None)

def memget(key, default=None):
	val = recall(key)
	if not val:
		pstr = "%s? "%(key,)
		if default:
			pstr = "%s[default: %s] "%(pstr, default)
		val = input(pstr) or default
		remember(key, val)
	return val

listeners = {}
def emit(channel, *data): # all cbs called, no return value
	if channel not in listeners:
		return print("%s: no one's listening"%(channel,))
	for cb in listeners[channel]:
		cb(*data)

def ask(channel, *data): # only 1st cb called, data returned
	if channel not in listeners:
		return print("%s: no one's listening"%(channel,))
	for cb in listeners[channel]:
		return cb(*data)

def listen(channel, cb):
	if channel not in listeners:
		listeners[channel] = []
	listeners[channel].append(cb)

OFFICE = None # not currently in use ... kinda gnarly
def getoffice(sub=None):
	if sub:
		return getattr(OFFICE, sub)
	return OFFICE

def setoffice(office):
	global OFFICE
	OFFICE = office

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

def getconf():
	from cantools.util.io import selnum
	print("noting Office defaults (%s), please select a configuration from the following presets.\n"%(predefs,))
	return selnum(presets)

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
DFP = "wss://api.dydx.exchange/v3/ws"
if STAGING:
	DFP = DFP.replace("api.", "api.stage.")
platforms = {
	"dacc": {
		"feed": DFP,
		"subber": ddaccount,
		"credHead": "/ws/accounts"
	},
	"dydx": {
		"feed": DFP,
		"subber": ddtrades # or ddorders
	},
	"chainrift": {
		"feed": "wss://ws.chainrift.com/v1",
		"subber": crsub
	},
	"gemini": {
		"feeder": lambda sname : "wss://api.gemini.com/v1/marketdata/%s"%(sname,)
	}
}

def feed(platname, streamname, **cbs): # {on_message,on_error,on_open,on_close}
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

def spew(event):
	log(json.dumps(event))

def start():
	rel.signal(2, rel.abort)
	rel.dispatch()

def stop():
	log("goodbye")
	if rel.is_running():
		rel.abort()
	else:
		sys.exit()