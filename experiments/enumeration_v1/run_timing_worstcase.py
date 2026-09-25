"""Enumeration timing on the handcrafted worst-case functions (parity, HWB, Q_V),
as a separate analysis. Uses rgr.dataset for the handcrafted examples.

Run: python experiments/enumeration/run_timing_worstcase.py
"""
import sys, os, csv, time, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from itertools import product
from rgr.dataset import load_examples, build_example
from rgr.enumerate import enumerate_reasons, node_dist
from rgr.reasons import all_prime_implicants, disagreement
from rgr.sdd_utils import term_to_sdd

OUT = os.path.join(os.path.dirname(__file__), "outputs"); os.makedirs(OUT, exist_ok=True)
clock = time.perf_counter; REPS = 3; MAX_NV = 10

def time_all(sdd, om, mgr, nv):
    ts=[]; t0=clock(); prev=t0; n=0
    for _ in enumerate_reasons(sdd, om, mgr, nv):
        now=clock(); ts.append(now-prev); prev=now; n+=1
    dl=ts[1:] if len(ts)>1 else ts
    return (clock()-t0), (max(dl) if dl else 0.0), (statistics.mean(dl) if dl else 0.0), n

def main():
    rows=[]
    for ex in load_examples():
        fam=ex["family"]
        if not fam.startswith("worst_case"): continue
        if ex["nvars"]>MAX_NV: continue
        grp = "parity" if fam=="worst_case_naive" else "hwb_qv"
        mgr,sdd,exb=build_example(ex); nv=exb["nvars"]
        pis=all_prime_implicants(sdd,nv,mgr)
        for bits in product([False,True],repeat=nv):
            om={i+1:bits[i] for i in range(nv)}
            if not (term_to_sdd(om,mgr)&sdd).is_false(): continue
            mind=min(disagreement(p,om) for p in pis)
            if sum(1 for p in pis if disagreement(p,om)==mind)<2: continue
            d0=node_dist(sdd,om,{})
            tm=clock()
            for _ in range(REPS):
                for _,_,dist in enumerate_reasons(sdd,om,mgr,nv):
                    if dist>d0: break
            t_min=(clock()-tm)/REPS
            t_all,mx,av,nall=time_all(sdd,om,mgr,nv)
            tn=clock()
            for _ in range(REPS): all_prime_implicants(sdd,nv,mgr)
            t_nv=(clock()-tn)/REPS
            rows.append({"id":exb["id"],"group":grp,"nvars":nv,
                "enum_minimal_us":t_min*1e6,"enum_all_us":t_all*1e6,"naive_all_us":t_nv*1e6,
                "max_delay_us":mx*1e6,"avg_delay_us":av*1e6})
    if not rows:
        print("no worst-case tie instances found"); return
    with open(os.path.join(OUT,"enum_timing_worstcase_results.csv"),"w",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    def m(k,s): return statistics.mean(r[k] for r in s)
    L=["Worst-case enumeration timing","="*40]
    for g in ["parity","hwb_qv"]:
        s=[r for r in rows if r["group"]==g]
        if not s: continue
        L.append(f"\n{g}:")
        for idv in sorted(set(r["id"] for r in s)):
            si=[r for r in s if r["id"]==idv]
            L.append(f"  {idv:10s} n={si[0]['nvars']:2d}  min {m('enum_minimal_us',si):8.1f}  all {m('enum_all_us',si):9.1f}  naive {m('naive_all_us',si):10.1f}  delay_max {m('max_delay_us',si):.1f}")
    txt="\n".join(L); open(os.path.join(OUT,"enum_timing_worstcase_summary.txt"),"w").write(txt+"\n"); print(txt)

if __name__=="__main__": main()