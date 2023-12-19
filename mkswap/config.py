class Config(object):
	def select(self):
		from cantools.util.io import selnum
		from .backend import predefs, presets
		print("\nnoting Office defaults (%s), please select a configuration from the following presets.\n"%(predefs,))
		return selnum(presets)

	def current(self):
		from .comptroller import ACTIVES_ALLOWED, LIVE
		from .office import VERBOSE, STAGISH
		from .base import UNSPAMMED
		from .backend import STAGING
		from .strategy import base, rsi, slosh
		from .harvester import SKIM, BATCH, BALANCE, NETWORK
		return {
			"harvester": {
				"skim": SKIM,
				"batch": BATCH,
				"balance": BALANCE,
				"network": NETWORK
			},
		    "comptroller": {
		        "actives": ACTIVES_ALLOWED,
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
		            "loud": base.LOUD
		        },
		        "rsi": {
		            "size": rsi.TRADE_SIZE,
		            "period": rsi.RSI_PERIOD
		        },
		        "slosh": {
		            "vmult": slosh.VOLATILITY_MULT
		        }
		    }
		}

	def set(self, c):
		from .comptroller import setActives, setLive
		from .office import setVerbose, setStagish
		from .backend import setStaging
		from .base import setUnspammed
		from .strategy import base, rsi, slosh
		from .harvester import setSkim, setBatch, setBalance, setNetwork
		s = { # live/staging/stagish should only be flipped by init()
			"harvester": {
				"skim": setSkim,
				"batch": setBatch,
				"balance": setBalance,
				"network": setNetwork
			},
		    "comptroller": {
		        "live": setLive,
		        "actives": setActives
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
		            "loud": base.setLoud
		        },
		        "rsi": {
		            "size": rsi.setSize,
		            "period": rsi.setPeriod
		        },
		        "slosh": {
		            "vmult": slosh.setVolatilityMult
		        }
		    }
		}
		print("CONFIG SET", c)
		while type(c) is dict:
			k = list(c.keys()).pop()
			s = s[k]
			c = c[k]
		s(c)

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