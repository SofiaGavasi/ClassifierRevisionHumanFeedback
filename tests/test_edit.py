"""Smoke tests for the engine on the two canonical fixtures."""
from rgr.sdd_utils import build, is_implicant
from rgr.edit import edit

def test_ab_or_c_edit_covers_omega():
    mgr, (a, b, c) = build(3)
    delta = (a & b) | c
    omega = {1: False, 2: False, 3: False}   # rejected
    res = edit(delta, omega, mgr, 3)
    assert res["distance"] == 1
    assert is_implicant(omega, res["edited"], mgr)  # now accepted
    assert (delta & ~res["edited"]).is_false()    # nothing lost

def test_wine_reason():
    mgr, (m, r, f, w) = build(4)
    delta = (~m) & (~f | w) & (w | r)
    omega = {1: True, 2: True, 3: True, 4: True}
    res = edit(delta, omega, mgr, 4)
    assert res["distance"] == 1
    assert res["weakened"] == {4: True}   # weakened reason is just w
