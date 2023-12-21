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
		from .base import UNSPAMMED
		from .backend import STAGING
		from .strategy import base, rsi, slosh
		from .harvester import SKIM, BATCH, BOTTOM, BALANCE, NETWORK
		return {
			"harvester": {
				"skim": SKIM,
				"batch": BATCH,
				"bottom": BOTTOM,
				"balance": BALANCE,
				"network": NETWORK
			},
		    "comptroller": {
		        "actives": ACTIVES_ALLOWED,
		        "prunelimit": PRUNE_LIMIT,
		        "live": LIVE
		    },
		    "backend": {
		        "staging": STAGING
		    },
		    "office": {
		        "verbose": VERBOSE,
		        "stagish": STAGISH
		    },
		    "base": {
		        "unspammed": UNSPAMMED
		    },
		    "strategy": {
		        "base": {
		            "inner": base.INNER,
		            "outer": base.OUTER,
		            "long": base.LONG,
		            "loud": base.LOUD
		        },
		        "rsi": {
		            "size": rsi.TRADE_SIZE,
		            "period": rsi.RSI_PERIOD
		        },
		        "slosh": {
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
		from .backend import setStaging
		from .base import setUnspammed
		from .strategy import base, rsi, slosh
		from .harvester import setSkim, setBatch, setBottom, setBalance, setNetwork
		s = { # live/staging/stagish should only be flipped by init()
			"harvester": {
				"skim": setSkim,
				"batch": setBatch,
				"bottom": setBottom,
				"balance": setBalance,
				"network": setNetwork
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
		    	"staging": setStaging
		    },
		    "base": {
		        "unspammed": setUnspammed
		    },
		    "strategy": {
		        "base": {
		            "inner": base.setInner,
		            "outer": base.setOuter,
		            "long": base.setLong,
		            "loud": base.setLoud
		        },
		        "rsi": {
		            "size": rsi.setSize,
		            "period": rsi.setPeriod
		        },
		        "slosh": {
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