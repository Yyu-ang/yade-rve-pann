import sys
sys.path.insert(0, "/home/hatch/workspace/yade-rve-pann/.worktrees/T05/w1")
import json
import numpy as np
from uq.material_uq import (load_model, mc_uq, interval_uq,
                            E_LO, E_HI, NU_LO, NU_HI)

model = load_model()
mc = mc_uq(model)
iv = interval_uq(model)

out = {"mc": mc, "interval": iv,
       "config": {"F": "diag(1.1,1,1)", "E": [E_LO, E_HI],
                  "nu": [NU_LO, NU_HI], "N": mc["n"], "seed": mc["seed"]}}
with open("/home/hatch/workspace/yade-rve-pann/for_worker/T05/w1/"
          "uq_results.json", "w") as f:
    json.dump(out, f, indent=2)

with open("/home/hatch/workspace/yade-rve-pann/for_worker/T05/w1/"
          "uq_results.json", "w") as f:
    json.dump(out, f, indent=2)
print("saved uq_results.json")
print("MC q99: pann=%.2f analytic=%.2f rel=%.3f%%"
      % (mc["pann"]["q99"], mc["analytic"]["q99"],
         100 * mc["rel_err"]["q99"]))
print("interval: pann=[%.2f, %.2f] analytic=[%.2f, %.2f]"
      % (iv["pann"]["min"], iv["pann"]["max"],
         iv["analytic"]["min"], iv["analytic"]["max"]))
