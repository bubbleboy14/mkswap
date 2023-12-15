class Config(object):
	def select(self):
		from cantools.util.io import selnum
		print("noting Office defaults (%s), please select a configuration from the following presets.\n"%(predefs,))
		return selnum(presets)

	def current(self):
		from .comptroller import ACTIVES_ALLOWED, LIVE
		from .office import VERBOSE
		from .base import UNSPAMMED
		from .backend import STAGING
		from .strategy import base, rsi, slosh
		return {
		    "comptroller": {
		        "actives": ACTIVES_ALLOWED,
		        "live": LIVE
		    },
		    "backend": {
		        "staging": STAGING
		    },
		    "office": {
		        "verbose": VERBOSE
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
		from .comptroller import setActive
		from .office import setVerbose
		from .base import setUnspammed
		from .strategy import base, rsi, slosh
		s = {
		    "comptroller": {
		        "actives": setActive
		    },
		    "office": {
		        "verbose": setVerbose
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
		while type(c) is dict:
			k = c.keys().pop()
			s = s[k]
			c = c[k]
		s(c)


config = Config()