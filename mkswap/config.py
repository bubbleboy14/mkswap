class Config(object):
	def select(self):
		from cantools.util.io import selnum
		from .backend import predefs, presets
		print("\nnoting Office defaults (%s), please select a configuration from the following presets.\n"%(predefs,))
		return selnum(presets)

	def get(self, *path):
		cur = self.current()
		for k in path:
			cur = cur[k]
		return cur

	def current(self):
		from .comptroller import ACTIVES_ALLOWED, PRUNE_LIMIT, LIVE
		from .office import VERBOSE, STAGISH
		from .accountant import CAPPED
		from .base import UNSPAMMED
		from .ndx import INNER, SHORT, LONG, OUTER
		from .strategy import base, rsi, slosh
		from .backend import STAGING, REALDIE, CREDSET
		from .harvester import SKIM, BATCH, BOTTOM, BALANCE, NETWORK
		return {
			"harvester": {
				"skim": SKIM,
				"batch": BATCH,
				"bottom": BOTTOM,
				"balance": BALANCE,
				"network": NETWORK
			},
			"accountant": {
				"capped": CAPPED
			},
			"comptroller": {
				"actives": ACTIVES_ALLOWED,
				"prunelimit": PRUNE_LIMIT,
				"live": LIVE
			},
			"backend": {
				"staging": STAGING,
				"realdie": REALDIE,
				"credset": CREDSET
			},
			"office": {
				"verbose": VERBOSE,
				"stagish": STAGISH
			},
			"base": {
				"unspammed": UNSPAMMED
			},
			"ndx": {
				"inner": INNER,
				"short": SHORT,
				"long": LONG,
				"outer": OUTER
			},
			"strategy": {
				"base": {
					"loud": base.LOUD
				},
				"rsi": {
					"size": rsi.TRADE_SIZE,
					"period": rsi.RSI_PERIOD
				},
				"slosh": {
					"oneswap": slosh.ONESWAP,
					"randlim": slosh.RANDLIM,
					"vmult": slosh.VOLATILITY_MULT,
					"vcutoff": slosh.VOLATILITY_CUTOFF
				}
			}
		}

	def _set(self, c, s):
		if type(c) is dict:
			for k in c.keys():
				self._set(c[k], s[k])
		else:
			s(c)

	def set(self, c):
		from .comptroller import setPruneLimit, setActives, setLive
		from .office import setVerbose, setStagish
		from .backend import setStaging, setRealDie, setCredSet
		from .accountant import setCapped
		from .base import setUnspammed
		from .strategy import base, rsi, slosh
		from .ndx import setInner, setShort, setLong, setOuter
		from .harvester import setSkim, setBatch, setBottom, setBalance, setNetwork
		s = { # live/staging/stagish/credset should only be flipped by init()
			"harvester": {
				"skim": setSkim,
				"batch": setBatch,
				"bottom": setBottom,
				"balance": setBalance,
				"network": setNetwork
			},
			"accountant": {
				"capped": setCapped
			},
			"comptroller": {
				"live": setLive,
				"actives": setActives,
				"prunelimit": setPruneLimit
			},
			"office": {
				"verbose": setVerbose,
				"stagish": setStagish
			},
			"backend": {
				"staging": setStaging,
				"realdie": setRealDie,
				"credset": setCredSet
			},
			"base": {
				"unspammed": setUnspammed
			},
			"ndx": {
				"inner": setInner,
				"short": setShort,
				"long": setLong,
				"outer": setOuter
			},
			"strategy": {
				"base": {
					"loud": base.setLoud
				},
				"rsi": {
					"size": rsi.setSize,
					"period": rsi.setPeriod
				},
				"slosh": {
					"oneswap": slosh.setOneSwap,
					"randlim": slosh.setRandLim,
					"vmult": slosh.setVolatilityMult,
					"vcutoff": slosh.setVolatilityCutoff
				}
			}
		}
		print("CONFIG SET", c)
		self._set(c, s)

	def init(self):
		from cantools.util.io import selnum
		cfg = {}
		if input("\nlive comptroller? [No/yes] ").lower().startswith("y"):
			cfg["comptroller"] = {
				"live": True
			}
		print("\nselect mode")
		mode = selnum(["staging", "stagish", "production"])
		if mode == "production":
			cfg["backend"] = {
				"staging": False
			}
		elif mode == "stagish":
			cfg["office"] = {
				"stagish": True
			}
		cfg and self.set(cfg)

config = Config()