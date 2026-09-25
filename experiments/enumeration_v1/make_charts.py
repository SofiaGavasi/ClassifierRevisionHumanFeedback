"""Paper-style charts for the enumeration timing experiments.
Reads the harness suite results (enum_timing_results.csv) and, if present, the
worst-case results (enum_timing_worstcase_results.csv)."""
import os, sys, csv, statistics
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams.update({"font.family":"serif","font.size":11,"axes.linewidth":0.8,
                 "xtick.direction":"in","ytick.direction":"in","legend.frameon":False})
OUT=os.path.join(os.path.dirname(__file__),"outputs")
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),"..",".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rgr.suite import load_suite, build_classifier

C={"min":"#4C6EF5","all":"#7048E8","naive":"#E8590C","delay":"#2B8A3E"}

def load(name):
    p=os.path.join(OUT,name)
    if not os.path.exists(p): return None
    rows=[]
    for r in csv.DictReader(open(p)):
        d={}
        for k,v in r.items():
            try: d[k]=float(v)
            except ValueError: d[k]=v
        d["nvars"]=int(d["nvars"]); rows.append(d)
    return rows

def add_sdd_sizes(rows):
    """Rebuild each classifier only to recover its SDD size."""
    suite = load_suite("standard")
    entries = {entry["id"]: entry for entry in suite["classifiers"]}

    needed = {(r["id"], r.get("vtree", "right")) for r in rows}
    sizes = {}

    for classifier_id, vtree in needed:
        entry = entries[classifier_id]
        _, sdd = build_classifier(entry, vtree_type=vtree)
        sizes[(classifier_id, vtree)] = sdd.size()

    for r in rows:
        vtree = r.get("vtree", "right")
        r["sdd_size"] = sizes[(r["id"], vtree)]

    return rows


def mbn(rows,key):
    ns=sorted(set(r["nvars"] for r in rows))
    return ns,[statistics.mean([r[key] for r in rows if r["nvars"]==n]) for n in ns]

def suite_charts(rows):
    # time vs n
    fig,ax=plt.subplots(figsize=(4.4,3.2))
    ns,ym=mbn(rows,"enum_minimal_us"); _,ya=mbn(rows,"enum_all_us"); _,yn=mbn(rows,"naive_all_us"); _,yd=mbn(rows,"avg_delay_us")
    ax.plot(ns,ym,"o-",color=C["min"],ms=4,lw=1.4,label="enum procedure: minimal reasons")
    ax.plot(ns,ya,"s-",color=C["all"],ms=4,lw=1.4,label="enum procedur: all reasons")
    ax.plot(ns,yn,"^-",color=C["naive"],ms=4,lw=1.4,label="naive PI enumeration")
    ax.plot(ns,yd,"o--",color=C["delay"],ms=4,lw=1.2,alpha=0.8,label="avg delay")
    ax.set_yscale("log"); ax.set_xlabel("number of features $n$"); ax.set_ylabel("time ($\\mu$s, log)")
    ax.set_xticks(ns); ax.legend(fontsize=8.5,loc="upper left"); fig.tight_layout()
    for e in("png",): fig.savefig(os.path.join(OUT,f"fig_time_vs_n.{e}"),dpi=200); 
    plt.close(fig)
    # delay vs n
    fig,ax=plt.subplots(figsize=(4.4,3.2))
    ns,ymx=mbn(rows,"max_delay_us"); _,yav=mbn(rows,"avg_delay_us")
    ax.plot(ns,ymx,"o-",color=C["delay"],ms=4,lw=1.4,label="max delay")
    ax.plot(ns,yav,"o--",color=C["delay"],ms=4,lw=1.2,alpha=0.7,label="avg delay")
    ax.set_xlabel("number of features $n$"); ax.set_ylabel("delay between reasons ($\\mu$s)")
    ax.set_xticks(ns); ax.legend(fontsize=8.5,loc="upper left"); fig.tight_layout()
    for e in("png",): fig.savefig(os.path.join(OUT,f"fig_delay_vs_n.{e}"),dpi=200)
    plt.close(fig)
    # speedup vs n
    fig,ax=plt.subplots(figsize=(4.4,3.2))
    ns=sorted(set(r["nvars"] for r in rows))
    sp=[statistics.mean([r["naive_all_us"]/max(1e-9,r["enum_minimal_us"]) for r in rows if r["nvars"]==n]) for n in ns]
    ax.plot(ns,sp,"o-",color=C["min"],ms=4,lw=1.4); ax.axhline(1,ls=":",color="gray",lw=1)
    ax.set_xlabel("number of features $n$"); ax.set_ylabel("speedup over naive (minimal task)")
    ax.set_xticks(ns); fig.tight_layout()
    for e in("png",): fig.savefig(os.path.join(OUT,f"fig_speedup_vs_n.{e}"),dpi=200)
    plt.close(fig)

    # --- polynomial-delay guarantee charts ---
    have_sdd = "sdd_size" in rows[0]

    if have_sdd:
        # Exclude zero-size SDDs from size-normalized plots.
        # A zero denominator cannot be meaningfully normalized.
        valid_rows = [r for r in rows if r["sdd_size"] > 0]
        excluded = len(rows) - len(valid_rows)

        if excluded:
            print(f"excluded {excluded} zero-size SDD rows from size-normalized plots")

        # (A) delay vs |D|, log-log
        fig,ax=plt.subplots(figsize=(4.4,3.2))

        xs=[r["sdd_size"] for r in valid_rows]
        ymax=[r["max_delay_us"] for r in valid_rows]
        yavg=[r["avg_delay_us"] for r in valid_rows]

        ax.scatter(xs,ymax,s=8,color=C["delay"],alpha=0.35,
                   edgecolors="none",label="max delay")
        ax.scatter(xs,yavg,s=8,color=C["min"],alpha=0.35,
                   edgecolors="none",label="avg delay")

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("compiled size $|D|$ (log)")
        ax.set_ylabel("delay ($\\mu$s, log)")
        ax.legend(fontsize=8.5,loc="upper left")
        fig.tight_layout()

        for e in ("png",):
            fig.savefig(os.path.join(OUT,f"fig_delay_vs_size.{e}"),dpi=200)

        plt.close(fig)

        # (B) delay / |D| vs n
        fig,ax=plt.subplots(figsize=(4.4,3.2))

        ns2=sorted(set(r["nvars"] for r in valid_rows))

        ymax_norm=[
            statistics.mean([
                r["max_delay_us"]/r["sdd_size"]
                for r in valid_rows
                if r["nvars"]==n
            ])
            for n in ns2
        ]

        yavg_norm=[
            statistics.mean([
                r["avg_delay_us"]/r["sdd_size"]
                for r in valid_rows
                if r["nvars"]==n
            ])
            for n in ns2
        ]

        ax.plot(ns2,ymax_norm,"o-",color=C["delay"],ms=4,lw=1.4,
                label="max delay / $|D|$")
        ax.plot(ns2,yavg_norm,"o--",color=C["min"],ms=4,lw=1.2,
                alpha=0.8,label="avg delay / $|D|$")

        ax.set_xlabel("number of features $n$")
        ax.set_ylabel("delay / $|D|$ ($\\mu$s per node)")
        ax.set_xticks(ns2)
        ax.legend(fontsize=8.5,loc="upper left")
        fig.tight_layout()

        for e in ("png",):
            fig.savefig(os.path.join(OUT,f"fig_delay_norm_vs_n.{e}"),dpi=200)

        plt.close(fig)

        # (C) delay / (n |D|) vs n
        # Individual classifiers are shown as faint points;
        # the line gives the mean at each n.
        fig,ax=plt.subplots(figsize=(4.4,3.2))

        ns3=sorted(set(r["nvars"] for r in valid_rows))

        x_ind=[r["nvars"] for r in valid_rows]

        max_ind=[
            r["max_delay_us"]/(r["nvars"]*r["sdd_size"])
            for r in valid_rows
        ]

        avg_ind=[
            r["avg_delay_us"]/(r["nvars"]*r["sdd_size"])
            for r in valid_rows
        ]

        ax.scatter(
            x_ind,
            max_ind,
            s=14,
            color=C["delay"],
            alpha=0.18,
            edgecolors="none"
        )

        ax.scatter(
            x_ind,
            avg_ind,
            s=14,
            color=C["min"],
            alpha=0.18,
            edgecolors="none"
        )

        max_norm_n=[
            statistics.mean([
                r["max_delay_us"]/(r["nvars"]*r["sdd_size"])
                for r in valid_rows
                if r["nvars"]==n
            ])
            for n in ns3
        ]

        avg_norm_n=[
            statistics.mean([
                r["avg_delay_us"]/(r["nvars"]*r["sdd_size"])
                for r in valid_rows
                if r["nvars"]==n
            ])
            for n in ns3
        ]

        ax.plot(
            ns3,
            max_norm_n,
            "o-",
            color=C["delay"],
            ms=4,
            lw=1.5,
            label="max delay / $(n|D|)$ mean"
        )

        ax.plot(
            ns3,
            avg_norm_n,
            "o--",
            color=C["min"],
            ms=4,
            lw=1.3,
            alpha=0.9,
            label="avg delay / $(n|D|)$ mean"
        )

        ax.set_xlabel("number of features $n$")
        ax.set_ylabel("delay / $(n|D|)$ ($\\mu$s per node-feature)")
        ax.set_xticks(ns3)
        ax.legend(fontsize=8.5,loc="upper left")
        fig.tight_layout()

        for e in ("png",):
            fig.savefig(os.path.join(OUT,f"fig_delay_norm_nD_vs_n.{e}"),dpi=200)

        plt.close(fig)

    # (D) delay vs total number of reasons (independence)
    if "n_all" in rows[0] or "n_tie_instances" in rows[0]:
        key="n_all" if "n_all" in rows[0] else "n_tie_instances"
        fig,ax=plt.subplots(figsize=(4.4,3.2))
        xs=[r[key] for r in rows]
        ys=[r["avg_delay_us"] for r in rows]
        ax.scatter(xs,ys,s=8,color=C["delay"],alpha=0.35,edgecolors="none")
        ax.set_xlabel("number of reasons")
        ax.set_ylabel("avg delay ($\\mu$s)")
        fig.tight_layout()

        for e in ("png",):
            fig.savefig(os.path.join(OUT,f"fig_delay_vs_reasons.{e}"),dpi=200)

        plt.close(fig)

def worstcase_chart(rows):
    fig,ax=plt.subplots(figsize=(4.8,3.2))
    for g,mk,cl in [("parity","o","#E8590C"),("hwb_qv","s","#7048E8")]:
        s=[r for r in rows if r["group"]==g]
        if not s: continue
        ns=sorted(set(r["nvars"] for r in s))
        ym=[statistics.mean([r["enum_minimal_us"] for r in s if r["nvars"]==n]) for n in ns]
        yn=[statistics.mean([r["naive_all_us"] for r in s if r["nvars"]==n]) for n in ns]
        ax.plot(ns,ym,mk+"-",color=cl,ms=4,lw=1.4,label=f"{g}: enum procedure minimal")
        ax.plot(ns,yn,mk+":",color=cl,ms=4,lw=1.2,alpha=0.6,label=f"{g}: naive")
    ax.set_yscale("log"); ax.set_xlabel("number of features $n$"); ax.set_ylabel("time ($\\mu$s, log)")
    ax.legend(fontsize=8,loc="upper left"); fig.tight_layout()
    for e in("png",): fig.savefig(os.path.join(OUT,f"fig_worstcase.{e}"),dpi=200)
    plt.close(fig)

def main():
    s=load("enumeration_results.csv")
    if s:
        print("reconstructing SDD sizes...")
        s=add_sdd_sizes(s)
        valid = [r for r in s if r["sdd_size"] > 0]

        print("\nLargest normalized delays:")

        for r in sorted(
            valid,
            key=lambda r:
                r["max_delay_us"] /
                (r["nvars"] * r["sdd_size"]),
            reverse=True
        )[:15]:

            ratio = (
                r["max_delay_us"] /
                (r["nvars"] * r["sdd_size"])
            )

            print(
                f"id={r['id']:8s} "
                f"n={r['nvars']:2d} "
                f"density={r['density']:4.2f} "
                f"|D|={r['sdd_size']:6.0f} "
                f"delay={r['max_delay_us']:9.2f} "
                f"normalized={ratio:9.2f}"
            )
        suite_charts(s)
        print("wrote suite charts")

    w=load("enum_timing_worstcase_results.csv")
    if w:
        worstcase_chart(w)
        print("wrote worst-case chart")

if __name__=="__main__": main()