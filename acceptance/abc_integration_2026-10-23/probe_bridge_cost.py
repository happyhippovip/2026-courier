"""Isolated probe (not in the repo): a bridge spec without any cost field is dispatched."""
import tests.test_ledger_v1_bridge as t


def test_probe_spec_without_cost_is_posted(tmp_path):
    http = t.FakeHTTP()
    spec = t._spec()
    assert "estimated_cost_eur" not in spec and "unknown_cost" not in spec
    home = t._home(tmp_path, {"A": spec})
    t._seed(home, [t._ready("A", "a-assign")])
    code, out, err, log, lines = t._run(home, http)
    assert code == 0, err
    assert len(http.posts) == 1          # dispatched without any cost decision


def test_probe_spec_marked_unknown_cost_is_posted(tmp_path):
    http = t.FakeHTTP()
    spec = t._spec(params={"unit": "a", "unknown_cost": True})
    home = t._home(tmp_path, {"A": spec})
    t._seed(home, [t._ready("A", "a-assign")])
    code, out, err, log, lines = t._run(home, http)
    print("code", code, "posts", len(http.posts))
