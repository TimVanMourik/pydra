import sys

from ..state import State

import pytest, pdb
python35_only = pytest.mark.skipif(sys.version_info < (3, 5), reason="requires Python>3.4")


@pytest.mark.parametrize("inputs, splitter, ndim, states_ind, states_val, group_for_inputs, "
                         "groups_stack", [
   ({"NA.a": [3, 5]}, "a", 1, [{'NA.a': 0}, {'NA.a': 1}],
    [{'NA.a': 3}, {'NA.a': 5}], {"NA.a": 0}, [[0]]),
    ({"NA.a": [3, 5], "NA.b": ["str1", "str2"]}, ("a", "b"), 1,
     [{'NA.a': 0, 'NA.b': 0}, {'NA.a': 1, 'NA.b': 1}],
     [{'NA.a': 3, 'NA.b': "str1"}, {'NA.a': 5, 'NA.b': "str2"}],
     {"NA.a": 0, "NA.b": 0}, [[0]]),
    ({"NA.a": [3, 5], "NA.b": ["str1", "str2"]}, ["a", "b"], 2,
     [{'NA.a': 0, 'NA.b': 0}, {'NA.a': 0, 'NA.b': 1},
      {'NA.a': 1, 'NA.b': 0}, {'NA.a': 1, 'NA.b': 1}],
     [{'NA.a': 3, 'NA.b': "str1"}, {'NA.a': 3, 'NA.b': "str2"},
      {'NA.a': 5, 'NA.b': "str1"}, {'NA.a': 5, 'NA.b': "str2"}],
     {"NA.a": 0, "NA.b": 1}, [[0, 1]]),
    ({"NA.a": [3, 5], "NA.b": ["str1", "str2"], "NA.c": [10, 20]}, [("a", "c"), "b"], 2,
     [{'NA.a': 0, 'NA.b': 0, "NA.c": 0}, {'NA.a': 0, 'NA.b': 1, "NA.c": 0},
      {'NA.a': 1, 'NA.b': 0, "NA.c": 1}, {'NA.a': 1, 'NA.b': 1, "NA.c": 1}],
     [{'NA.a': 3, 'NA.b': "str1", "NA.c": 10}, {'NA.a': 3, 'NA.b': "str2", "NA.c": 10},
      {'NA.a': 5, 'NA.b': "str1", "NA.c": 20}, {'NA.a': 5, 'NA.b': "str2", "NA.c": 20}],
      {"NA.a": 0, "NA.c": 0, "NA.b": 1}, [[0, 1]])
])
def test_state_1(inputs, splitter, ndim, states_ind, states_val, group_for_inputs, groups_stack):
    st = State(name="NA", splitter=splitter)
    assert st.group_for_inputs_final == group_for_inputs
    assert st.groups_stack_final == groups_stack

    st.prepare_states(inputs)
    assert st.states_ind == states_ind
    assert st.states_val == states_val


def test_state_merge_1():
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", other_states={"NA": (st1, "b")})
    assert st2.splitter == "_NA"
    assert st2.splitter_rpn == ["NA.a"]
    assert st2.group_for_inputs_final == {"NA.a": 0}
    assert st2.groups_stack_final == [[0]]

    st2.prepare_states(inputs={"NA.a": [3, 5]})
    assert st2.states_ind == [{'NA.a': 0}, {'NA.a': 1}]
    assert st2.states_val == [{'NA.a': 3}, {'NA.a': 5}]


def test_state_merge_1a():
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter="_NA", other_states={"NA": (st1, "b")})
    assert st2.splitter == "_NA"
    assert st2.splitter_rpn == ["NA.a"]
    assert st2.group_for_inputs_final == {"NA.a": 0}
    assert st2.groups_stack_final == [[0]]

    st2.prepare_states(inputs={"NA.a": [3, 5]})
    assert st2.states_ind == [{'NA.a': 0}, {'NA.a': 1}]
    assert st2.states_val == [{'NA.a': 3}, {'NA.a': 5}]


def test_state_merge_1b_exception():
    """can't provide explicitly NA.a"""
    st1 = State(name="NA", splitter="a")
    with pytest.raises(Exception) as excinfo:
        st2 = State(name="NB", splitter="NA.a")
    assert 'consider using _NA' in str(excinfo.value)


@pytest.mark.parametrize("splitter2, other_states2", [
    ("_NA", {}),
    ("_N", {"NA": ()})
])
def test_state_merge_1c_exception(splitter2, other_states2):
    """can't ask for splitter from node that is not connected"""
    st1 = State(name="NA", splitter="a")
    with pytest.raises(Exception) as excinfo:
        st2 = State(name="NB", splitter=splitter2, other_states=other_states2)
    assert 'other nodes that are connected' in str(excinfo.value)


def test_state_merge_2():
    """state2 has Left and Right part"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["_NA", "a"], other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", "NB.a"]
    assert st2.splitter_rpn == ["NA.a", "NB.a", "*"]
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.a": 1}
    assert st2.groups_stack_final == [[0, 1]]
    assert st2.keys_final == ["NA.a", "NB.a"]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.a": [1, 2]})
    assert st2.states_ind == [{'NA.a': 0, "NB.a": 0}, {'NA.a': 0, "NB.a": 1},
                              {'NA.a': 1, "NB.a": 0}, {'NA.a': 1, "NB.a": 1}]
    assert st2.states_val == [{'NA.a': 3, "NB.a": 1}, {'NA.a': 3, "NB.a": 2},
                              {'NA.a': 5, "NB.a": 1}, {'NA.a': 5, "NB.a": 2}]


def test_state_merge_2a():
    """adding scalar to st2"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["_NA", "a"], other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", "NB.a"]
    assert st2.splitter_rpn == ["NA.a", "NB.a", "*"]
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.a": 1}
    assert st2.groups_stack_final == [[0, 1]]
    assert st2.keys_final == ["NA.a", "NB.a"]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.a": [1, 2], "NB.s": 1})
    assert st2.states_ind == [{'NA.a': 0, "NB.a": 0}, {'NA.a': 0, "NB.a": 1},
                              {'NA.a': 1, "NB.a": 0}, {'NA.a': 1, "NB.a": 1}]
    assert st2.states_val == [{'NA.a': 3, "NB.a": 1}, {'NA.a': 3, "NB.a": 2},
                              {'NA.a': 5, "NB.a": 1}, {'NA.a': 5, "NB.a": 2}]


def test_state_merge_2b():
    """splitter st2 has only Right part, Left has to be added"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter="a", other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", "NB.a"]
    assert st2.splitter_rpn == ["NA.a", "NB.a", "*"]
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.a": 1}
    assert st2.groups_stack_final == [[0, 1]]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.a": [1, 2]})
    assert st2._right_splitter == "NB.a"
    assert st2._left_splitter == "_NA"
    assert st2.states_ind == [{'NA.a': 0, "NB.a": 0}, {'NA.a': 0, "NB.a": 1},
                              {'NA.a': 1, "NB.a": 0}, {'NA.a': 1, "NB.a": 1}]
    assert st2.states_val == [{'NA.a': 3, "NB.a": 1}, {'NA.a': 3, "NB.a": 2},
                              {'NA.a': 5, "NB.a": 1}, {'NA.a': 5, "NB.a": 2}]


def test_state_merge_3():
    """two states connected with st3, no splitter provided - Left has to be added"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter="a")
    st3 = State(name="NC", other_states={"NA": (st1, "b"), "NB": (st2, "c")})

    assert st3.splitter == ["_NA", "_NB"]
    assert st3.splitter_rpn == ["NA.a", "NB.a", "*"]
    assert st3.group_for_inputs_final == {"NA.a": 0, "NB.a": 1}
    assert st3.groups_stack_final == [[0, 1]]

    st3.prepare_states(inputs={"NA.a": [3, 5], "NB.a": [30, 50]})
    assert st3.states_ind == [{'NA.a': 0, "NB.a": 0}, {'NA.a': 0, "NB.a": 1},
                              {'NA.a': 1, "NB.a": 0}, {'NA.a': 1, "NB.a": 1}]
    assert st3.states_val == [{'NA.a': 3, "NB.a": 30}, {'NA.a': 3, "NB.a": 50},
                              {'NA.a': 5, "NB.a": 30}, {'NA.a': 5, "NB.a": 50}]


def test_state_merge_3a():
    """two states connected with st3, Left splitter provided"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter="a")
    st3 = State(name="NC", splitter=["_NA", "_NB"], other_states={"NA": (st1, "b"), "NB": (st2, "c")})

    assert st3.splitter == ["_NA", "_NB"]
    assert st3.splitter_rpn == ["NA.a", "NB.a", "*"]
    assert st3.group_for_inputs_final == {"NA.a": 0, "NB.a": 1}
    assert st3.groups_stack_final == [[0, 1]]

    st3.prepare_states(inputs={"NA.a": [3, 5], "NB.a": [30, 50]})
    assert st3.states_ind == [{'NA.a': 0, "NB.a": 0}, {'NA.a': 0, "NB.a": 1},
                              {'NA.a': 1, "NB.a": 0}, {'NA.a': 1, "NB.a": 1}]
    assert st3.states_val == [{'NA.a': 3, "NB.a": 30}, {'NA.a': 3, "NB.a": 50},
                              {'NA.a': 5, "NB.a": 30}, {'NA.a': 5, "NB.a": 50}]


def test_state_merge_3b():
    """two states connected with st3, partial Left splitter provided"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter="a")
    st3 = State(name="NC", splitter="_NB", other_states={"NA": (st1, "b"), "NB": (st2, "c")})

    assert st3.splitter == ["_NA", "_NB"]
    assert st3.splitter_rpn == ["NA.a", "NB.a", "*"]
    assert st3.group_for_inputs_final == {"NA.a": 0, "NB.a": 1}
    assert st3.groups_stack_final == [[0, 1]]

    st3.prepare_states(inputs={"NA.a": [3, 5], "NB.a": [30, 50]})
    assert st3.states_ind == [{'NA.a': 0, "NB.a": 0}, {'NA.a': 0, "NB.a": 1},
                              {'NA.a': 1, "NB.a": 0}, {'NA.a': 1, "NB.a": 1}]
    assert st3.states_val == [{'NA.a': 3, "NB.a": 30}, {'NA.a': 3, "NB.a": 50},
                              {'NA.a': 5, "NB.a": 30}, {'NA.a': 5, "NB.a": 50}]

@pytest.mark.xfail(reason="splitter has scallar in left part - groups don't work properly")
def test_state_merge_3c():
    """two states connected with st3, scalar Left splitter provided"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter="a")
    st3 = State(name="NC", splitter=("_NA", "_NB"), other_states={"NA": (st1, "b"), "NB": (st2, "c")})

    assert st3.splitter == ("_NA", "_NB")
    assert st3.splitter_rpn == ["NA.a", "NB.a", "."]
    assert st3.group_for_inputs_final == {"NA.a": 0, "NB.a": 0}
    assert st3.groups_stack_final == [[0]]

    st3.prepare_states(inputs={"NA.a": [3, 5], "NB.a": [30, 50]})
    assert st3.states_ind == [{'NA.a': 0, "NB.a": 0}, {'NA.a': 1, "NB.a": 1}]
    assert st3.states_val == [{'NA.a': 3, "NB.a": 30}, {'NA.a': 5, "NB.a": 50}]


def test_state_merge_4():
    """one previous node, but with outer splitter"""
    st1 = State(name="NA", splitter=["a", "b"])
    st2 = State(name="NB", other_states={"NA": (st1, "a")})
    assert st2.splitter == "_NA"
    assert st2.splitter_rpn == ["NA.a", "NA.b", "*"]
    assert st2.group_for_inputs_final == {"NA.a": 0, "NA.b": 1}
    assert st2.groups_stack_final == [[0, 1]]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NA.b": [10, 20]})
    assert st2.states_ind == [{'NA.a': 0, "NA.b": 0}, {'NA.a': 0, "NA.b": 1},
                              {'NA.a': 1, "NA.b": 0}, {'NA.a': 1, "NA.b": 1}]
    assert st2.states_val == [{'NA.a': 3, "NA.b": 10}, {'NA.a': 3, "NA.b": 20},
                              {'NA.a': 5, "NA.b": 10}, {'NA.a': 5, "NA.b": 20}]


def test_state_merge_5():
    """two previous nodes, one with outer splitter, full Left part provided"""
    st1 = State(name="NA", splitter=["a", "b"])
    st2 = State(name="NB", splitter="a")
    st3 = State(name="NC", splitter=["_NA", "_NB"], other_states={"NA": (st1, "a"), "NB": (st2, "b")})
    assert st3.splitter == ["_NA", "_NB"]
    assert st3.splitter_rpn == ["NA.a", "NA.b", "*", "NB.a", "*"]
    assert st3.group_for_inputs_final == {"NA.a": 0, "NA.b": 1, "NB.a": 2}
    assert st3.groups_stack_final == [[0, 1, 2]]

    st3.prepare_states(inputs={"NA.a": [3, 5], "NA.b": [10, 20], "NB.a": [600, 700]})

    assert st3.states_ind == [{'NA.a': 0, 'NA.b': 0, "NB.a": 0}, {'NA.a': 0, 'NA.b': 0, "NB.a": 1},
                              {'NA.a': 0, 'NA.b': 1, "NB.a": 0}, {'NA.a': 0, 'NA.b': 1, "NB.a": 1},
                              {'NA.a': 1, 'NA.b': 0, "NB.a": 0}, {'NA.a': 1, 'NA.b': 0, "NB.a": 1},
                              {'NA.a': 1, 'NA.b': 1, "NB.a": 0}, {'NA.a': 1, 'NA.b': 1, "NB.a": 1}]
    assert st3.states_val == [{'NA.a': 3, 'NA.b': 10, "NB.a": 600}, {'NA.a': 3, 'NA.b': 10, "NB.a": 700},
                              {'NA.a': 3, 'NA.b': 20, "NB.a": 600}, {'NA.a': 3, 'NA.b': 20, "NB.a": 700},
                              {'NA.a': 5, 'NA.b': 10, "NB.a": 600}, {'NA.a': 5, 'NA.b': 10, "NB.a": 700},
                              {'NA.a': 5, 'NA.b': 20, "NB.a": 600}, {'NA.a': 5, 'NA.b': 20, "NB.a": 700}]


def test_state_merge_5a():
    """two previous nodes, one with outer splitter, no splitter - Left part has to be added"""
    st1 = State(name="NA", splitter=["a", "b"])
    st2 = State(name="NB", splitter="a")
    st3 = State(name="NC", other_states={"NA": (st1, "a"), "NB": (st2, "b")})
    assert st3.splitter == ["_NA", "_NB"]
    assert st3.splitter_rpn == ["NA.a", "NA.b", "*", "NB.a", "*"]
    assert st3.group_for_inputs_final == {"NA.a": 0, "NA.b": 1, "NB.a": 2}
    assert st3.groups_stack_final == [[0, 1, 2]]

    st3.prepare_states(inputs={"NA.a": [3, 5], "NA.b": [10, 20], "NB.a": [600, 700]})
    assert st3.states_ind == [{'NA.a': 0, 'NA.b': 0, "NB.a": 0}, {'NA.a': 0, 'NA.b': 0, "NB.a": 1},
                              {'NA.a': 0, 'NA.b': 1, "NB.a": 0}, {'NA.a': 0, 'NA.b': 1, "NB.a": 1},
                              {'NA.a': 1, 'NA.b': 0, "NB.a": 0}, {'NA.a': 1, 'NA.b': 0, "NB.a": 1},
                              {'NA.a': 1, 'NA.b': 1, "NB.a": 0}, {'NA.a': 1, 'NA.b': 1, "NB.a": 1}]
    assert st3.states_val == [{'NA.a': 3, 'NA.b': 10, "NB.a": 600}, {'NA.a': 3, 'NA.b': 10, "NB.a": 700},
                              {'NA.a': 3, 'NA.b': 20, "NB.a": 600}, {'NA.a': 3, 'NA.b': 20, "NB.a": 700},
                              {'NA.a': 5, 'NA.b': 10, "NB.a": 600}, {'NA.a': 5, 'NA.b': 10, "NB.a": 700},
                              {'NA.a': 5, 'NA.b': 20, "NB.a": 600}, {'NA.a': 5, 'NA.b': 20, "NB.a": 700}]


def test_state_merge_innerspl_1():
    """one previous node and one inner splitter; full splitter provided"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["_NA", "b"], other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", "NB.b"]
    assert st2.splitter_rpn == ["NA.a", "NB.b", "*"]
    assert st2.other_states["NA"][1] == "b"
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.b": 1}
    assert st2.groups_stack_final == [[0], [1]]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.b": [[1, 10, 100], [2, 20, 200]]})

    assert st2.states_ind == \
           [{'NA.a': 0, "NB.b": 0}, {'NA.a': 0, "NB.b": 1}, {'NA.a': 0, "NB.b": 2},
            {'NA.a': 1, "NB.b": 3}, {'NA.a': 1, "NB.b": 4}, {'NA.a': 1, "NB.b": 5}]
    assert st2.states_val == \
           [{'NA.a': 3, "NB.b": 1}, {'NA.a': 3, "NB.b": 10}, {'NA.a': 3, "NB.b": 100},
            {'NA.a': 5, "NB.b": 2}, {'NA.a': 5, "NB.b": 20}, {'NA.a': 5, "NB.b": 200},]


def test_state_merge_innerspl_1a():
    """one previous node and one inner splitter; only Right part provided - Left had to be added"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter="b", other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", "NB.b"]
    assert st2.splitter_rpn == ["NA.a", "NB.b", "*"]
    assert st2.other_states["NA"][1] == "b"
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.b": 1}
    assert st2.groups_stack_final == [[0], [1]]


    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.b": [[1, 10, 100], [2, 20, 200]]})

    assert st2.states_ind == [{'NA.a': 0, "NB.b": 0}, {'NA.a': 0, "NB.b": 1}, {'NA.a': 0, "NB.b": 2},
                              {'NA.a': 1, "NB.b": 3}, {'NA.a': 1, "NB.b": 4}, {'NA.a': 1, "NB.b": 5}]
    assert st2.states_val == [{'NA.a': 3, "NB.b": 1}, {'NA.a': 3, "NB.b": 10}, {'NA.a': 3, "NB.b": 100},
                              {'NA.a': 5, "NB.b": 2}, {'NA.a': 5, "NB.b": 20}, {'NA.a': 5, "NB.b": 200},]


def test_state_merge_innerspl_1b():
    """one previous node and one inner splitter;
    incorrect splitter - Right & Left parts in scalar splitter"""
    with pytest.raises(Exception):
        st1 = State(name="NA", splitter="a")
        st2 = State(name="NB", splitter=("_NA", "b"), other_states={"NA": (st1, "b")})


def test_state_merge_innerspl_3():
    """one previous node and one inner splitter; only Right part provided - Left had to be added"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["c", "b"], other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", ["NB.c", "NB.b"]]
    assert st2.splitter_rpn == ["NA.a", "NB.c", "NB.b", "*", "*"]
    assert st2.other_states["NA"][1] == "b"
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.c": 1, "NB.b": 2}
    assert st2.groups_stack_final == [[0], [1, 2]]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.b": [[1, 10, 100], [2, 20, 200]], "NB.c": [13, 17]})
    assert st2.states_ind == [
        {'NB.c': 0, 'NA.a': 0, "NB.b": 0}, {'NB.c': 0, 'NA.a': 0, "NB.b": 1}, {'NB.c': 0, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 0, 'NA.a': 1, "NB.b": 3}, {'NB.c': 0, 'NA.a': 1, "NB.b": 4}, {'NB.c': 0, 'NA.a': 1, "NB.b": 5},
        {'NB.c': 1, 'NA.a': 0, "NB.b": 0}, {'NB.c': 1, 'NA.a': 0, "NB.b": 1}, {'NB.c': 1, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 1, 'NA.a': 1, "NB.b": 3}, {'NB.c': 1, 'NA.a': 1, "NB.b": 4}, {'NB.c': 1, 'NA.a': 1, "NB.b": 5}
    ]
    assert st2.states_val == [
        {'NB.c': 13, 'NA.a': 3, "NB.b": 1}, {'NB.c': 13, 'NA.a': 3, "NB.b": 10}, {'NB.c': 13, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 13, 'NA.a': 5, "NB.b": 2}, {'NB.c': 13, 'NA.a': 5, "NB.b": 20}, {'NB.c': 13, 'NA.a': 5, "NB.b": 200},
        {'NB.c': 17, 'NA.a': 3, "NB.b": 1}, {'NB.c': 17, 'NA.a': 3, "NB.b": 10}, {'NB.c': 17, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 17, 'NA.a': 5, "NB.b": 2}, {'NB.c': 17, 'NA.a': 5, "NB.b": 20}, {'NB.c': 17, 'NA.a': 5, "NB.b": 200}
    ]


def test_state_merge_innerspl_3a():
    """
    one previous node and one inner splitter; only Right part provided - Left had to be added;
    different order in splitter in st2
    """
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["b", "c"], other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", ["NB.b", "NB.c"]]
    assert st2.splitter_rpn == ["NA.a", "NB.b", "NB.c", "*", "*"]
    assert st2.other_states["NA"][1] == "b"
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.c": 2, "NB.b": 1}
    assert st2.groups_stack_final == [[0], [1, 2]]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.b": [[1, 10, 100], [2, 20, 200]], "NB.c": [13, 17]})

    assert st2.states_ind == [
        {'NB.c': 0, 'NA.a': 0, "NB.b": 0}, {'NB.c': 1, 'NA.a': 0, "NB.b": 0}, {'NB.c': 0, 'NA.a': 0, "NB.b": 1},
        {'NB.c': 1, 'NA.a': 0, "NB.b": 1}, {'NB.c': 0, 'NA.a': 0, "NB.b": 2}, {'NB.c': 1, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 0, 'NA.a': 1, "NB.b": 3}, {'NB.c': 1, 'NA.a': 1, "NB.b": 3}, {'NB.c': 0, 'NA.a': 1, "NB.b": 4},
        {'NB.c': 1, 'NA.a': 1, "NB.b": 4}, {'NB.c': 0, 'NA.a': 1, "NB.b": 5},{'NB.c': 1, 'NA.a': 1, "NB.b": 5}
    ]

    assert st2.states_val == [
        {'NB.c': 13, 'NA.a': 3, "NB.b": 1}, {'NB.c': 17, 'NA.a': 3, "NB.b": 1}, {'NB.c': 13, 'NA.a': 3, "NB.b": 10},
        {'NB.c': 17, 'NA.a': 3, "NB.b": 10}, {'NB.c': 13, 'NA.a': 3, "NB.b": 100}, {'NB.c': 17, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 13, 'NA.a': 5, "NB.b": 2}, {'NB.c': 17, 'NA.a': 5, "NB.b": 2}, {'NB.c': 13, 'NA.a': 5, "NB.b": 20},
        {'NB.c': 17, 'NA.a': 5, "NB.b": 20}, {'NB.c': 13, 'NA.a': 5, "NB.b": 200}, {'NB.c': 17, 'NA.a': 5, "NB.b": 200}
    ]



def test_state_merge_innerspl_4():
    """
    two previous nodes connected serially and one inner splitter;
    only Right part provided - Left had to be added
    """
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["c", "b"], other_states={"NA": (st1, "b")})
    st3 = State(name="NC", splitter="d", other_states={"NB": (st2, "a")})

    assert st3.splitter == ["_NB", "NC.d"]
    assert st3.splitter_rpn == ["NA.a", "NB.c", "NB.b", "*", "*", "NC.d", "*"]
    assert st3.group_for_inputs_final == {"NA.a": 0, "NB.c": 1, "NB.b": 2, "NC.d": 3}
    assert st3.groups_stack_final == [[0], [1, 2, 3]]

    st3.prepare_states(
        inputs={"NA.a": [3, 5], "NB.b": [[1, 10, 100], [2, 20, 200]], "NB.c": [13, 17], "NC.d": [33, 77]})

    assert st2.states_ind == [
        {'NB.c': 0, 'NA.a': 0, "NB.b": 0}, {'NB.c': 0, 'NA.a': 0, "NB.b": 1}, {'NB.c': 0, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 0, 'NA.a': 1, "NB.b": 3}, {'NB.c': 0, 'NA.a': 1, "NB.b": 4}, {'NB.c': 0, 'NA.a': 1, "NB.b": 5},
        {'NB.c': 1, 'NA.a': 0, "NB.b": 0}, {'NB.c': 1, 'NA.a': 0, "NB.b": 1}, {'NB.c': 1, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 1, 'NA.a': 1, "NB.b": 3}, {'NB.c': 1, 'NA.a': 1, "NB.b": 4}, {'NB.c': 1, 'NA.a': 1, "NB.b": 5}
    ]
    assert st2.states_val == [
        {'NB.c': 13, 'NA.a': 3, "NB.b": 1}, {'NB.c': 13, 'NA.a': 3, "NB.b": 10}, {'NB.c': 13, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 13, 'NA.a': 5, "NB.b": 2}, {'NB.c': 13, 'NA.a': 5, "NB.b": 20}, {'NB.c': 13, 'NA.a': 5, "NB.b": 200},
        {'NB.c': 17, 'NA.a': 3, "NB.b": 1}, {'NB.c': 17, 'NA.a': 3, "NB.b": 10}, {'NB.c': 17, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 17, 'NA.a': 5, "NB.b": 2}, {'NB.c': 17, 'NA.a': 5, "NB.b": 20}, {'NB.c': 17, 'NA.a': 5, "NB.b": 200}
    ]

    assert st3.states_ind == [
        {'NB.c': 0, 'NA.a': 0, "NB.b": 0, "NC.d": 0}, {'NB.c': 0, 'NA.a': 0, "NB.b": 0, "NC.d": 1},
        {'NB.c': 0, 'NA.a': 0, "NB.b": 1, "NC.d": 0}, {'NB.c': 0, 'NA.a': 0, "NB.b": 1, "NC.d": 1},
        {'NB.c': 0, 'NA.a': 0, "NB.b": 2, "NC.d": 0}, {'NB.c': 0, 'NA.a': 0, "NB.b": 2, "NC.d": 1},
        {'NB.c': 0, 'NA.a': 1, "NB.b": 3, "NC.d": 0}, {'NB.c': 0, 'NA.a': 1, "NB.b": 3, "NC.d": 1},
        {'NB.c': 0, 'NA.a': 1, "NB.b": 4, "NC.d": 0}, {'NB.c': 0, 'NA.a': 1, "NB.b": 4, "NC.d": 1},
        {'NB.c': 0, 'NA.a': 1, "NB.b": 5, "NC.d": 0}, {'NB.c': 0, 'NA.a': 1, "NB.b": 5, "NC.d": 1},
        {'NB.c': 1, 'NA.a': 0, "NB.b": 0, "NC.d": 0}, {'NB.c': 1, 'NA.a': 0, "NB.b": 0, "NC.d": 1},
        {'NB.c': 1, 'NA.a': 0, "NB.b": 1, "NC.d": 0}, {'NB.c': 1, 'NA.a': 0, "NB.b": 1, "NC.d": 1},
        {'NB.c': 1, 'NA.a': 0, "NB.b": 2, "NC.d": 0}, {'NB.c': 1, 'NA.a': 0, "NB.b": 2, "NC.d": 1},
        {'NB.c': 1, 'NA.a': 1, "NB.b": 3, "NC.d": 0}, {'NB.c': 1, 'NA.a': 1, "NB.b": 3, "NC.d": 1},
        {'NB.c': 1, 'NA.a': 1, "NB.b": 4, "NC.d": 0}, {'NB.c': 1, 'NA.a': 1, "NB.b": 4, "NC.d": 1},
        {'NB.c': 1, 'NA.a': 1, "NB.b": 5, "NC.d": 0}, {'NB.c': 1, 'NA.a': 1, "NB.b": 5, "NC.d": 1}
    ]
    assert st3.states_val == [
        {'NB.c': 13, 'NA.a': 3, "NB.b": 1, "NC.d": 33}, {'NB.c': 13, 'NA.a': 3, "NB.b": 1, "NC.d": 77},
        {'NB.c': 13, 'NA.a': 3, "NB.b": 10, "NC.d": 33}, {'NB.c': 13, 'NA.a': 3, "NB.b": 10, "NC.d": 77},
        {'NB.c': 13, 'NA.a': 3, "NB.b": 100, "NC.d": 33}, {'NB.c': 13, 'NA.a': 3, "NB.b": 100, "NC.d": 77},
        {'NB.c': 13, 'NA.a': 5, "NB.b": 2, "NC.d": 33}, {'NB.c': 13, 'NA.a': 5, "NB.b": 2, "NC.d": 77},
        {'NB.c': 13, 'NA.a': 5, "NB.b": 20, "NC.d": 33}, {'NB.c': 13, 'NA.a': 5, "NB.b": 20, "NC.d": 77},
        {'NB.c': 13, 'NA.a': 5, "NB.b": 200, "NC.d": 33}, {'NB.c': 13, 'NA.a': 5, "NB.b": 200, "NC.d":77},
        {'NB.c': 17, 'NA.a': 3, "NB.b": 1, "NC.d": 33}, {'NB.c': 17, 'NA.a': 3, "NB.b": 1, "NC.d": 77},
        {'NB.c': 17, 'NA.a': 3, "NB.b": 10, "NC.d": 33}, {'NB.c': 17, 'NA.a': 3, "NB.b": 10, "NC.d": 77},
        {'NB.c': 17, 'NA.a': 3, "NB.b": 100, "NC.d": 33}, {'NB.c': 17, 'NA.a': 3, "NB.b": 100, "NC.d": 77},
        {'NB.c': 17, 'NA.a': 5, "NB.b": 2, "NC.d": 33}, {'NB.c': 17, 'NA.a': 5, "NB.b": 2, "NC.d": 77},
        {'NB.c': 17, 'NA.a': 5, "NB.b": 20, "NC.d": 33}, {'NB.c': 17, 'NA.a': 5, "NB.b": 20, "NC.d": 77},
        {'NB.c': 17, 'NA.a': 5, "NB.b": 200, "NC.d": 33}, {'NB.c': 17, 'NA.a': 5, "NB.b": 200, "NC.d": 77}
    ]


def test_state_merge_innerspl_5():
    """two previous nodes and one inner splitter; only Right part provided - Left had to be added"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["b", "c"])
    st3 = State(name="NC", splitter="d", other_states={"NA": (st1, "e"), "NB": (st2, "f")})

    assert st3.splitter == [["_NA", "_NB"], "NC.d"]
    assert st3.splitter_rpn == ["NA.a", "NB.b", "NB.c", "*", "*", "NC.d", "*"]
    assert st3.other_states["NA"][1] == "e"
    assert st3.other_states["NB"][1] == "f"
    assert st3.group_for_inputs_final == {"NA.a": 0, "NB.c": 2, "NB.b": 1, "NC.d": 3}
    assert st3.groups_stack_final == [[0, 1, 2, 3]]

    st3.prepare_states(inputs={"NA.a": [3, 5], "NB.b": [10, 20], "NB.c": [13, 17],
                               "NC.e": [30, 50], "NC.f": [[23, 27], [33, 37]], "NC.d": [1, 2]})
    assert st3.states_ind == [
        {"NA.a": 0, "NB.b": 0, "NB.c": 0, "NC.d": 0}, {"NA.a": 0, "NB.b": 0, "NB.c": 0, "NC.d": 1},
        {"NA.a": 0, "NB.b": 0, "NB.c": 1, "NC.d": 0}, {"NA.a": 0, "NB.b": 0, "NB.c": 1, "NC.d": 1},
        {"NA.a": 0, "NB.b": 1, "NB.c": 0, "NC.d": 0}, {"NA.a": 0, "NB.b": 1, "NB.c": 0, "NC.d": 1},
        {"NA.a": 0, "NB.b": 1, "NB.c": 1, "NC.d": 0}, {"NA.a": 0, "NB.b": 1, "NB.c": 1, "NC.d": 1},
        {"NA.a": 1, "NB.b": 0, "NB.c": 0, "NC.d": 0}, {"NA.a": 1, "NB.b": 0, "NB.c": 0, "NC.d": 1},
        {"NA.a": 1, "NB.b": 0, "NB.c": 1, "NC.d": 0}, {"NA.a": 1, "NB.b": 0, "NB.c": 1, "NC.d": 1},
        {"NA.a": 1, "NB.b": 1, "NB.c": 0, "NC.d": 0}, {"NA.a": 1, "NB.b": 1, "NB.c": 0, "NC.d": 1},
        {"NA.a": 1, "NB.b": 1, "NB.c": 1, "NC.d": 0}, {"NA.a": 1, "NB.b": 1, "NB.c": 1, "NC.d": 1},
    ]

    assert st3.states_val == [
        {"NA.a": 3, "NB.b": 10, "NB.c": 13, "NC.d": 1}, {"NA.a": 3, "NB.b": 10, "NB.c": 13, "NC.d": 2},
        {"NA.a": 3, "NB.b": 10, "NB.c": 17, "NC.d": 1}, {"NA.a": 3, "NB.b": 10, "NB.c": 17, "NC.d": 2},
        {"NA.a": 3, "NB.b": 20, "NB.c": 13, "NC.d": 1}, {"NA.a": 3, "NB.b": 20, "NB.c": 13, "NC.d": 2},
        {"NA.a": 3, "NB.b": 20, "NB.c": 17, "NC.d": 1}, {"NA.a": 3, "NB.b": 20, "NB.c": 17, "NC.d": 2},
        {"NA.a": 5, "NB.b": 10, "NB.c": 13, "NC.d": 1}, {"NA.a": 5, "NB.b": 10, "NB.c": 13, "NC.d": 2},
        {"NA.a": 5, "NB.b": 10, "NB.c": 17, "NC.d": 1}, {"NA.a": 5, "NB.b": 10, "NB.c": 17, "NC.d": 2},
        {"NA.a": 5, "NB.b": 20, "NB.c": 13, "NC.d": 1}, {"NA.a": 5, "NB.b": 20, "NB.c": 13, "NC.d": 2},
        {"NA.a": 5, "NB.b": 20, "NB.c": 17, "NC.d": 1}, {"NA.a": 5, "NB.b": 20, "NB.c": 17, "NC.d": 2},
    ]


def test_state_combine_1():
    """the simplest splitter and combiner"""
    st = State(name="NA", splitter="a", combiner="a")
    assert st.splitter == "NA.a"
    assert st.splitter_rpn == ["NA.a"]
    assert st.combiner == ["NA.a"]
    assert st.splitter_final == None
    assert st.splitter_rpn_final == []
    assert st.group_for_inputs_final == {}
    assert st.groups_stack_final == []

    st.prepare_states(inputs={"NA.a": [3, 5]})
    assert st.states_ind == [{"NA.a": 0}, {"NA.a": 1}]
    assert st.states_val == [{"NA.a": 3}, {"NA.a": 5}]


def test_state_combine_2():
    """two connected states; outer splitter and combiner in the first one"""
    st1 = State(name="NA", splitter=["a", "b"], combiner="a")
    st2 = State(name="NB", other_states={"NA": (st1, "c")})

    assert st1.splitter == ["NA.a", "NA.b"]
    assert st1.splitter_rpn == ["NA.a", "NA.b", "*"]
    assert st1.combiner == ["NA.a"]
    assert st2.splitter == "_NA"
    assert st2.splitter_rpn == ["NA.b"]
    assert st2.group_for_inputs_final == {"NA.b": 0}
    assert st2.groups_stack_final == [[0]]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NA.b": [10, 20]})
    assert st1.states_ind == [{"NA.a": 0, "NA.b": 0}, {"NA.a": 0, "NA.b": 1},
                              {"NA.a": 1, "NA.b": 0}, {"NA.a": 1, "NA.b": 1}]
    assert st1.states_val == [{"NA.a": 3, "NA.b": 10}, {"NA.a": 3, "NA.b": 20},
                              {"NA.a": 5, "NA.b": 10}, {"NA.a": 5, "NA.b": 20}]

    assert st2.states_ind == [{"NA.b": 0}, {"NA.b": 1}]
    assert st2.states_val == [{"NA.b": 10}, {"NA.b": 20}]


def test_state_combine_3():
    """
    two connected states; outer splitter and combiner in the first one;
    additional splitter in the second node
    """
    st1 = State(name="NA", splitter=["a", "b"], combiner="a")
    st2 = State(name="NB", splitter="d", other_states={"NA": (st1, "c")})

    assert st1.splitter == ["NA.a", "NA.b"]
    assert st1.splitter_rpn == ["NA.a", "NA.b", "*"]
    assert st1.combiner == ["NA.a"]
    assert st1.splitter_final == "NA.b"
    assert st1.splitter_rpn_final == ["NA.b"]

    assert st2.splitter == ["_NA", "NB.d"]
    assert st2.splitter_rpn == ["NA.b", "NB.d", "*"]
    assert st2.group_for_inputs_final == {"NA.b": 0, "NB.d": 1}
    assert st2.groups_stack_final == [[0, 1]]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NA.b": [10, 20], "NB.c": [90, 150], "NB.d": [0, 1]})
    assert st1.states_ind == [{"NA.a": 0, "NA.b": 0}, {"NA.a": 0, "NA.b": 1},
                              {"NA.a": 1, "NA.b": 0}, {"NA.a": 1, "NA.b": 1}]
    assert st1.states_val == [{"NA.a": 3, "NA.b": 10}, {"NA.a": 3, "NA.b": 20},
                              {"NA.a": 5, "NA.b": 10}, {"NA.a": 5, "NA.b": 20}]

    assert st2.states_ind == [{"NA.b": 0, "NB.d": 0}, {"NA.b": 0, "NB.d": 1},
                              {"NA.b": 1, "NB.d": 0}, {"NA.b": 1, "NB.d": 1}]
    assert st2.states_val == [{"NA.b": 10, "NB.d": 0}, {"NA.b": 10, "NB.d": 1},
                              {"NA.b": 20, "NB.d": 0}, {"NA.b": 20, "NB.d": 1}]

def test_state_combine_4():
    """
    two connected states; outer splitter and combiner in the first one;
    additional splitter in the second node
    """
    st1 = State(name="NA", splitter=["a", "b"], combiner="a")
    st2 = State(name="NB", splitter="d", combiner="d", other_states={"NA": (st1, "c")})

    assert st1.splitter == ["NA.a", "NA.b"]
    assert st1.splitter_rpn == ["NA.a", "NA.b", "*"]
    assert st1.combiner == ["NA.a"]
    assert st1.splitter_final == "NA.b"
    assert st1.splitter_rpn_final == ["NA.b"]

    assert st2.splitter == ["_NA", "NB.d"]
    assert st2.splitter_rpn == ["NA.b", "NB.d", "*"]
    assert st2.splitter_rpn_final == ["NA.b"]
    assert st2.group_for_inputs_final == {"NA.b": 0}
    assert st2.groups_stack_final == [[0]]


    st2.prepare_states(inputs={"NA.a": [3, 5], "NA.b": [10, 20], "NB.c": [90, 150], "NB.d": [0, 1]})

    assert st1.states_ind == [{"NA.a": 0, "NA.b": 0}, {"NA.a": 0, "NA.b": 1},
                              {"NA.a": 1, "NA.b": 0}, {"NA.a": 1, "NA.b": 1}]
    assert st1.states_val == [{"NA.a": 3, "NA.b": 10}, {"NA.a": 3, "NA.b": 20},
                              {"NA.a": 5, "NA.b": 10}, {"NA.a": 5, "NA.b": 20}]

    assert st2.states_ind == [{"NA.b": 0, "NB.d": 0}, {"NA.b": 0, "NB.d": 1},
                              {"NA.b": 1, "NB.d": 0}, {"NA.b": 1, "NB.d": 1}]
    assert st2.states_val == [{"NA.b": 10, "NB.d": 0}, {"NA.b": 10, "NB.d": 1},
                              {"NA.b": 20, "NB.d": 0}, {"NA.b": 20, "NB.d": 1}]


def test_state_combine_innerspl_1():
    """one previous node and one inner splitter; only Right part provided - Left had to be added"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["c", "b"], combiner=["b"], other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", ["NB.c", "NB.b"]]
    assert st2.splitter_rpn == ["NA.a", "NB.c", "NB.b", "*", "*"]
    assert st2.splitter_final == ["_NA", "NB.c"]
    assert st2.splitter_rpn_final == ["NA.a", "NB.c", "*"]
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.c": 1}
    assert st2.groups_stack_final == [[0], [1]]
    # TODO: i think at the end I should merge [0] and [1], because there are no inner splitters anymore
    # TODO: didn't include it in my code...
    #assert st2.groups_stack_final == [[0, 1]]


    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.b": [[1, 10, 100], [2, 20, 200]], "NB.c": [13, 17]})
    # NOW TODO: checking st2.states_ind_final!!!
    assert st2.states_ind == [
        {'NB.c': 0, 'NA.a': 0, "NB.b": 0}, {'NB.c': 0, 'NA.a': 0, "NB.b": 1}, {'NB.c': 0, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 0, 'NA.a': 1, "NB.b": 3}, {'NB.c': 0, 'NA.a': 1, "NB.b": 4}, {'NB.c': 0, 'NA.a': 1, "NB.b": 5},
        {'NB.c': 1, 'NA.a': 0, "NB.b": 0}, {'NB.c': 1, 'NA.a': 0, "NB.b": 1}, {'NB.c': 1, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 1, 'NA.a': 1, "NB.b": 3}, {'NB.c': 1, 'NA.a': 1, "NB.b": 4}, {'NB.c': 1, 'NA.a': 1, "NB.b": 5}
    ]
    assert st2.states_val == [
        {'NB.c': 13, 'NA.a': 3, "NB.b": 1}, {'NB.c': 13, 'NA.a': 3, "NB.b": 10}, {'NB.c': 13, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 13, 'NA.a': 5, "NB.b": 2}, {'NB.c': 13, 'NA.a': 5, "NB.b": 20}, {'NB.c': 13, 'NA.a': 5, "NB.b": 200},
        {'NB.c': 17, 'NA.a': 3, "NB.b": 1}, {'NB.c': 17, 'NA.a': 3, "NB.b": 10}, {'NB.c': 17, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 17, 'NA.a': 5, "NB.b": 2}, {'NB.c': 17, 'NA.a': 5, "NB.b": 20}, {'NB.c': 17, 'NA.a': 5, "NB.b": 200}
    ]


def test_state_combine_innerspl_2():
    """one previous node and one inner splitter; only Right part provided - Left had to be added"""
    st1 = State(name="NA", splitter="a")
    st2 = State(name="NB", splitter=["c", "b"], combiner=["c"], other_states={"NA": (st1, "b")})

    assert st2.splitter == ["_NA", ["NB.c", "NB.b"]]
    assert st2.splitter_rpn == ["NA.a", "NB.c", "NB.b", "*", "*"]
    assert st2.splitter_final == ["_NA", "NB.b"]
    assert st2.splitter_rpn_final == ["NA.a", "NB.b", "*"]
    assert st2.group_for_inputs_final == {"NA.a": 0, "NB.b": 1}
    assert st2.groups_stack_final == [[0], [1]]

    st2.prepare_states(inputs={"NA.a": [3, 5], "NB.b": [[1, 10, 100], [2, 20, 200]], "NB.c": [13, 17]})
    assert st2.states_ind == [
        {'NB.c': 0, 'NA.a': 0, "NB.b": 0}, {'NB.c': 0, 'NA.a': 0, "NB.b": 1}, {'NB.c': 0, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 0, 'NA.a': 1, "NB.b": 3}, {'NB.c': 0, 'NA.a': 1, "NB.b": 4}, {'NB.c': 0, 'NA.a': 1, "NB.b": 5},
        {'NB.c': 1, 'NA.a': 0, "NB.b": 0}, {'NB.c': 1, 'NA.a': 0, "NB.b": 1}, {'NB.c': 1, 'NA.a': 0, "NB.b": 2},
        {'NB.c': 1, 'NA.a': 1, "NB.b": 3}, {'NB.c': 1, 'NA.a': 1, "NB.b": 4}, {'NB.c': 1, 'NA.a': 1, "NB.b": 5}
    ]
    assert st2.states_val == [
        {'NB.c': 13, 'NA.a': 3, "NB.b": 1}, {'NB.c': 13, 'NA.a': 3, "NB.b": 10}, {'NB.c': 13, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 13, 'NA.a': 5, "NB.b": 2}, {'NB.c': 13, 'NA.a': 5, "NB.b": 20}, {'NB.c': 13, 'NA.a': 5, "NB.b": 200},
        {'NB.c': 17, 'NA.a': 3, "NB.b": 1}, {'NB.c': 17, 'NA.a': 3, "NB.b": 10}, {'NB.c': 17, 'NA.a': 3, "NB.b": 100},
        {'NB.c': 17, 'NA.a': 5, "NB.b": 2}, {'NB.c': 17, 'NA.a': 5, "NB.b": 20}, {'NB.c': 17, 'NA.a': 5, "NB.b": 200}
    ]




# def test_state_merge_inner_1():
#     st1 = State(name="NA", splitter="a", inputs={"a": [3, 5]})
#     st2 = State(name="NB", others=[{"state": st1, "in_field": "b"}])
#     assert st2.splitter == "NA.a"
#     st2.prepare_states_ind()


        # assert st._splitter_rpn == ["NA.a"]
    # assert st.splitter_comb is None
    # assert st._splitter_rpn_comb == []
    #
    # st.prepare_state_input()
    #
    # expected_axis_for_input = {"NA.a": [0]}
    # for key, val in expected_axis_for_input.items():
    #     assert st._axis_for_input[key] == val
    # assert st._ndim == 1
    # assert st._input_for_axis == [["NA.a"]]
    #
    #
    # expected_axis_for_input_comb = {}
    # for key, val in expected_axis_for_input_comb.items():
    #     assert st._axis_for_input_comb[key] == val
    # assert st._ndim_comb == 0
    # assert st._input_for_axis_comb == []



# def test_state_1():
#     nd = Node(name="NA", interface=fun_addtwo(), splitter="a", combiner="a",
#               inputs={"a": np.array([3, 5])})
#     st = State(node=nd)
#
#     assert st._splitter == "NA.a"
#     assert st._splitter_rpn == ["NA.a"]
#     assert st.splitter_comb is None
#     assert st._splitter_rpn_comb == []
#
#     st.prepare_state_input()
#
#     expected_axis_for_input = {"NA.a": [0]}
#     for key, val in expected_axis_for_input.items():
#         assert st._axis_for_input[key] == val
#     assert st._ndim == 1
#     assert st._input_for_axis == [["NA.a"]]
#
#
#     expected_axis_for_input_comb = {}
#     for key, val in expected_axis_for_input_comb.items():
#         assert st._axis_for_input_comb[key] == val
#     assert st._ndim_comb == 0
#     assert st._input_for_axis_comb == []
#
#
# def test_state_1a():
#     wf = Workflow(name="wf", workingdir="wf_test", splitter="a", combiner="a",
#                   inputs={"a": np.array([3, 5])})
#     st = State(node=wf)
#
#     assert st._splitter == "wf.a"
#     assert st._splitter_rpn == ["wf.a"]
#     assert st.splitter_comb is None
#     assert st._splitter_rpn_comb == []
#
#     st.prepare_state_input()
#
#     expected_axis_for_input = {"wf.a": [0]}
#     for key, val in expected_axis_for_input.items():
#         assert st._axis_for_input[key] == val
#     assert st._ndim == 1
#     assert st._input_for_axis == [["wf.a"]]
#
#
#     expected_axis_for_input_comb = {}
#     for key, val in expected_axis_for_input_comb.items():
#         assert st._axis_for_input_comb[key] == val
#     assert st._ndim_comb == 0
#     assert st._input_for_axis_comb == []
#
#
# def test_state_2():
#     nd = Node(name="NA", interface=fun_addvar(), splitter=("a", "b"), combiner="a",
#               inputs={"a": np.array([3, 5]), "b": np.array([3, 5])})
#     st = State(node=nd)
#
#     assert st._splitter == ("NA.a", "NA.b")
#     assert st._splitter_rpn == ["NA.a", "NA.b", "."]
#     assert st.splitter_comb is None
#     assert st._splitter_rpn_comb == []
#
#     st.prepare_state_input()
#
#     expected_axis_for_input = {"NA.a": [0], "NA.b": [0]}
#     for key, val in expected_axis_for_input.items():
#         assert st._axis_for_input[key] == val
#     assert st._ndim == 1
#     assert st._input_for_axis == [["NA.a", "NA.b"]]
#
#
#     expected_axis_for_input_comb = {}
#     for key, val in expected_axis_for_input_comb.items():
#         assert st._axis_for_input_comb[key] == val
#     assert st._ndim_comb == 0
#     assert st._input_for_axis_comb == []
#
#
# def test_state_2a():
#     wf = Workflow(name="wf", workingdir="wf_test", splitter=("a", "b"), combiner="a",
#               inputs={"a": np.array([3, 5]), "b": np.array([3, 5])})
#     st = State(node=wf)
#
#     assert st._splitter == ("wf.a", "wf.b")
#     assert st._splitter_rpn == ["wf.a", "wf.b", "."]
#     assert st.splitter_comb is None
#     assert st._splitter_rpn_comb == []
#
#     st.prepare_state_input()
#
#     expected_axis_for_input = {"wf.a": [0], "wf.b": [0]}
#     for key, val in expected_axis_for_input.items():
#         assert st._axis_for_input[key] == val
#     assert st._ndim == 1
#     assert st._input_for_axis == [["wf.a", "wf.b"]]
#
#
#     expected_axis_for_input_comb = {}
#     for key, val in expected_axis_for_input_comb.items():
#         assert st._axis_for_input_comb[key] == val
#     assert st._ndim_comb == 0
#     assert st._input_for_axis_comb == []
#
#
# def test_state_3():
#     nd = Node(name="NA", interface=fun_addvar(), splitter=["a", "b"], combiner="a",
#               inputs={"a": np.array([3, 5]), "b": np.array([3, 5])})
#     st = State(node=nd)
#
#     assert st._splitter == ["NA.a", "NA.b"]
#     assert st._splitter_rpn == ["NA.a", "NA.b", "*"]
#     assert st.splitter_comb == "NA.b"
#     assert st._splitter_rpn_comb == ["NA.b"]
#
#     st.prepare_state_input()
#
#     expected_axis_for_input = {"NA.a": [0], "NA.b": [1]}
#     for key, val in expected_axis_for_input.items():
#         assert st._axis_for_input[key] == val
#     assert st._ndim == 2
#     assert st._input_for_axis == [["NA.a"], ["NA.b"]]
#
#
#     expected_axis_for_input_comb = {"NA.b": [0]}
#     for key, val in expected_axis_for_input_comb.items():
#         assert st._axis_for_input_comb[key] == val
#     assert st._ndim_comb == 1
#     assert st._input_for_axis_comb == [["NA.b"]]
#
#
# def test_state_4():
#     nd = Node(name="NA", interface=fun_addvar3(), splitter=["a", ("b", "c")], combiner="b",
#               inputs={"a": np.array([3, 5]), "b": np.array([3, 5]), "c": np.array([3, 5])})
#     st = State(node=nd)
#
#     assert st._splitter == ["NA.a", ("NA.b", "NA.c")]
#     assert st._splitter_rpn == ["NA.a", "NA.b", "NA.c", ".", "*"]
#     assert st.splitter_comb == "NA.a"
#     assert st._splitter_rpn_comb == ["NA.a"]
#
#     st.prepare_state_input()
#
#     expected_axis_for_input = {"NA.a": [0], "NA.b": [1], "NA.c": [1]}
#     for key, val in expected_axis_for_input.items():
#         assert st._axis_for_input[key] == val
#     assert st._ndim == 2
#     assert st._input_for_axis == [["NA.a"], ["NA.b", "NA.c"]]
#
#
#     expected_axis_for_input_comb = {"NA.a": [0]}
#     for key, val in expected_axis_for_input_comb.items():
#         assert st._axis_for_input_comb[key] == val
#     assert st._ndim_comb == 1
#     assert st._input_for_axis_comb == [["NA.a"]]
#
#
# def test_state_5():
#     nd = Node(name="NA", interface=fun_addvar3(), splitter=("a", ["b", "c"]), combiner="b",
#               inputs={"a": np.array([[3, 5], [3, 5]]), "b": np.array([3, 5]),
#                       "c": np.array([3, 5])})
#     st = State(node=nd)
#
#     assert st._splitter == ("NA.a", ["NA.b", "NA.c"])
#     assert st._splitter_rpn == ["NA.a", "NA.b", "NA.c", "*", "."]
#     assert st.splitter_comb == "NA.c"
#     assert st._splitter_rpn_comb == ["NA.c"]
#
#     st.prepare_state_input()
#
#     expected_axis_for_input = {"NA.a": [0, 1], "NA.b": [0], "NA.c": [1]}
#     for key, val in expected_axis_for_input.items():
#         assert st._axis_for_input[key] == val
#     assert st._ndim == 2
#     expected_input_for_axis = [["NA.a", "NA.b"], ["NA.a", "NA.c"]]
#     for (i, exp_l) in enumerate(expected_input_for_axis):
#         exp_l.sort()
#         st._input_for_axis[i].sort()
#     assert st._input_for_axis[i] == exp_l
#
#
#     expected_axis_for_input_comb = {"NA.c": [0]}
#     for key, val in expected_axis_for_input_comb.items():
#         assert st._axis_for_input_comb[key] == val
#     assert st._ndim_comb == 1
#     assert st._input_for_axis_comb == [["NA.c"]]
