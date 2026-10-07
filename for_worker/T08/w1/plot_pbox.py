"""Fig. 7 analogue p-box plot (paper Fig. 7 style).

x = sigma_char [MPa], y = probability.
Four boundaries: ref/PANN x lower/upper interval optimum (mu_E^i).
q99 markers on each boundary. Saved as PNG + quantile CSV.

Usage (pilot):  python for_worker/T08/w1/plot_pbox.py pilot
Usage (full) :  python for_worker/T08/w1/plot_pbox.py full
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

Q_LEVELS = [0.50, 0.90, 0.95, 0.99]
FIGDIR = os.path.join(ROOT, "figures", "T08")


def load_npz(tag, workdir):
    d = np.load(os.path.join(workdir, f"{tag}.npz"), allow_pickle=True)
    return d["sigma_char"], float(d["q99"]), float(d["mu"])


def pbox_data(workdir, prefix, mus):
    """Return dict[(const, mu)] -> (quantiles, q99)."""
    out = {}
    for mu in mus:
        for const in ["ref", "pann"]:
            tag = f"{prefix}_mu{mu:.1e}_{const}"
            sc, q99, _ = load_npz(tag, workdir)
            sc = sc[np.isfinite(sc)]
            out[(const, mu)] = (np.quantile(sc, Q_LEVELS), q99)
    return out


def plot_pbox(data, mus, png_path, title_suffix=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    mu_lo, mu_hi = min(mus), max(mus)
    fig, ax = plt.subplots(figsize=(9, 6))
    styles = {("ref", mu_lo): ("C0", "-", "ref, lower bound"),
              ("ref", mu_hi): ("C0", "--", "ref, upper bound"),
              ("pann", mu_lo): ("C1", "-", "PANN, lower bound"),
              ("pann", mu_hi): ("C1", "--", "PANN, upper bound")}
    for (const, mu), (qs, q99) in sorted(data.items()):
        color, ls, label = styles[(const, mu)]
        ax.plot(qs, Q_LEVELS, color=color, ls=ls, lw=2, label=label)
        ax.plot([q99], [0.99], color=color, marker="D", ms=8, mec="k")
    ax.set_xlabel(r"$\sigma_{\mathrm{char}}$ [MPa]")
    ax.set_ylabel("probability")
    ax.set_title("p-box of " + r"$\sigma_{\mathrm{char}}$"
                 + " \u2014 2D plane-stress analogue of paper Fig. 7\n"
                 + "(Harazin et al., CMAME 452 (2026) 118726)" + title_suffix,
                 fontsize=11)
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    print(f"wrote {png_path}")


def write_csv(data, mus, csv_path):
    mu_lo, mu_hi = min(mus), max(mus)
    import csv
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["constitutive", "mu_E_i_MPa"] +
                   [f"q{int(q*100)}_MPa" for q in Q_LEVELS])
        for const in ["ref", "pann"]:
            for mu in [mu_lo, mu_hi]:
                qs, _ = data[(const, mu)]
                w.writerow([const, f"{mu:.1e}"] +
                           [f"{v:.2f}" for v in qs])
        w.writerow([])
        w.writerow(["bound", "q99_ref_MPa", "q99_pann_MPa", "rel_err"])
        for mu, bound in [(mu_lo, "lower"), (mu_hi, "upper")]:
            qr = data[("ref", mu)][1]
            qp = data[("pann", mu)][1]
            w.writerow([bound, f"{qr:.2f}", f"{qp:.2f}",
                        f"{(qp-qr)/qr:+.4%}"])
    print(f"wrote {csv_path}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "pilot"
    workdir = os.path.join(ROOT, "for_worker", "T08", "w1")
    os.makedirs(FIGDIR, exist_ok=True)
    if mode == "pilot":
        mus = [2.8e4, 3.0e4, 3.2e4]
        data = pbox_data(workdir, "pilot", mus)
        # preliminary p-box uses the interval endpoints as bounds
        bdata = {k: v for k, v in data.items() if k[1] in (2.8e4, 3.2e4)}
        plot_pbox(bdata, [2.8e4, 3.2e4],
                  os.path.join(FIGDIR, "fig7_analog_pilot.png"),
                  title_suffix="\n(preliminary: pilot, 2000 samples/eval)")
        write_csv(bdata, [2.8e4, 3.2e4],
                  os.path.join(FIGDIR, "fig7_analog_pilot.csv"))
    elif mode == "full":
        mus = [2.8e4, 3.2e4]
        data = pbox_data(workdir, "full", mus)
        plot_pbox(data, mus, os.path.join(FIGDIR, "fig7_analog.png"))
        write_csv(data, mus, os.path.join(FIGDIR, "fig7_analog.csv"))
    else:
        raise ValueError(mode)


if __name__ == "__main__":
    main()
