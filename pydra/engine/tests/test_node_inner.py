import sys, os
import numpy as np
from pathlib import Path

from nipype.utils.filemanip import save_json, makedirs, to_str
from nipype.interfaces import fsl
from nipype import Function

from ..node import NodeBase, Workflow
from ..submitter import Submitter
from ..task import to_task

import pytest
import pdb

python35_only = pytest.mark.skipif(
    sys.version_info < (3, 5), reason="requires Python>3.4"
)

pytestmark = pytest.mark.xfail(reason="wip")


@pytest.fixture(scope="module")
def change_dir(request):
    orig_dir = os.getcwd()
    test_dir = os.path.join(orig_dir, "test_outputs_inner")
    makedirs(test_dir, exist_ok=True)
    os.chdir(test_dir)

    def move2orig():
        os.chdir(orig_dir)

    request.addfinalizer(move2orig)


Plugins = ["serial", "mp", "cf", "dask"]
Plugins = ["serial"]


@to_task
def fun_addtwo(a):
    import time

    time.sleep(1)
    if a == 3:
        time.sleep(2)
    return a + 2


@to_task
def fun_addvar(b, c):
    return b + c


@to_task
def fun_expans(a):
    return list(range(int(a)))


@to_task
def fun_sumlist(el_list):
    return sum(el_list)


@to_task
def fun_list_generator(n):
    return list(range(n))


@to_task
def fun_list_generator_10(n):
    return list(range(10, 10 + n))


# tests with nodes (or workflows with the nodes) that returns a list (length depends on the input)


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_inner_1(change_dir, plugin):
    """Node with interface that returns a list"""
    nn = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        inputs={"n": 3},
        workingdir="test_inner1_{}".format(plugin),
        output_names=["out"],
    )
    assert nn.inputs["NA.n"] == 3

    sub = Submitter(plugin=plugin, runnable=nn)
    sub.run()
    sub.close()

    assert nn.result["out"] == ({}, [0, 1, 2])


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_inner_2(change_dir, plugin):
    """Node with interface that returns a list, a simple splitter"""
    nn = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        inputs={"n": [3, 5]},
        workingdir="test_inner2_{}".format(plugin),
        output_names=["out"],
    )
    nn.split(splitter="n")
    assert (nn.inputs["NA.n"] == [3, 5]).all()

    sub = Submitter(plugin=plugin, runnable=nn)
    sub.run()
    sub.close()

    expected = [({"NA.n": 3}, [0, 1, 2]), ({"NA.n": 5}, [0, 1, 2, 3, 4])]
    for i, res in enumerate(expected):
        assert nn.result["out"][i][0] == res[0]
        assert nn.result["out"][i][1] == res[1]


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_inner_3(change_dir, plugin):
    """Node with interface that returns a list, a simple splitter and combiner"""
    nn = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        inputs={"n": [3, 5]},
        workingdir="test_inner2_{}".format(plugin),
        output_names=["out"],
    )
    nn.split(splitter="n")
    nn.combine(combiner="n")
    assert (nn.inputs["NA.n"] == [3, 5]).all()

    sub = Submitter(plugin=plugin, runnable=nn)
    sub.run()
    sub.close()

    assert nn.result["out"] == ({}, [[0, 1, 2], [0, 1, 2, 3, 4]])


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_1(change_dir, plugin):
    """wf with a single nd with an interface that returns a list"""
    wf = Workflow(
        name="wf1",
        workingdir="test_innerwf1_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": 3},
    )
    wf.add_nodes([na])

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    assert wf.nodes[0].result["out"] == ({}, [0, 1, 2])
    # output of the wf
    assert wf.result["NA_out"] == ({}, [0, 1, 2])


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_2(change_dir, plugin):
    """wf with a single nd with an interface that returns a list, a simple splitter"""
    wf = Workflow(
        name="wf2",
        workingdir="test_innerwf2_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    wf.add_nodes([na])

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    expected = [({"NA.n": 3}, [0, 1, 2]), ({"NA.n": 5}, [0, 1, 2, 3, 4])]
    for i, res in enumerate(expected):
        assert wf.nodes[0].result["out"][i][0] == res[0]
        assert wf.nodes[0].result["out"][i][1] == res[1]

    # output of the wf
    for i, res in enumerate(expected):
        assert wf.result["NA_out"][i][0] == res[0]
        assert wf.result["NA_out"][i][1] == res[1]


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_3(change_dir, plugin):
    """wf with two nodes, the first one returns a list,
    the second takes entire list as an input
    """
    wf = Workflow(
        name="wf3",
        workingdir="test_innerwf3_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NB", "out", "NB_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": 3},
    )
    nb = NodeBase(
        name="NB", interface=fun_sumlist(), workingdir="nb", output_names=["out"]
    )
    wf.add_nodes([na, nb])
    wf.connect("NA", "out", "NB", "el_list")

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    assert wf.nodes[0].result["out"] == ({}, [0, 1, 2])
    assert wf.nodes[1].result["out"] == ({}, 3)
    # output of the wf
    assert wf.result["NA_out"] == ({}, [0, 1, 2])
    assert wf.result["NB_out"] == ({}, 3)


# tests that have wf with multiple nodes and inner splitter


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_4(change_dir, plugin):
    """wf with two nodes, the first one returns a list,
    the second takes elements of the list as an input - has a simple inner splitter and combiner
    """
    wf = Workflow(
        name="wf4",
        workingdir="test_innerwf4_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NB", "out", "NB_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": 3},
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    wf.add_nodes([na, nb])
    wf.connect("NA", "out", "NB", "a")
    nb.split(splitter="a").combine(combiner="a")

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    assert wf.nodes[0].result["out"] == ({}, [0, 1, 2])
    assert wf.nodes[1].result["out"] == ({}, [2, 3, 4])
    # output of the wf
    assert wf.result["NA_out"] == ({}, [0, 1, 2])
    assert wf.result["NB_out"] == ({}, [2, 3, 4])


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_5(change_dir, plugin):
    """wf with two nodes, the first one has a splitter and each element returns a list,
    the second takes elements of the list as an input - has a simple inner splitter and combiner
    """
    wf = Workflow(
        name="wf5",
        workingdir="test_innerwf5_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NB", "out", "NB_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    wf.add_nodes([na, nb])
    wf.connect("NA", "out", "NB", "a")
    nb.split(splitter=["a", "NA.n"]).combine(combiner="a")

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    assert wf.nodes[0].result["out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.nodes[1].result["out"] == [
        ({"NA.n": 3}, [2, 3, 4]),
        ({"NA.n": 5}, [2, 3, 4, 5, 6]),
    ]
    # output of the wf
    assert wf.result["NA_out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.result["NB_out"] == [
        ({"NA.n": 3}, [2, 3, 4]),
        ({"NA.n": 5}, [2, 3, 4, 5, 6]),
    ]


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_5a(change_dir, plugin):
    """wf with two nodes, the first one has a splitter and each element returns a list,
    the second takes elements of the list as an input - has a simple inner splitter
    and combiner that includes inner splitter and state splitter
    """
    wf = Workflow(
        name="wf5a",
        workingdir="test_innerwf5a_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NB", "out", "NB_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    wf.add_nodes([na, nb])
    wf.connect("NA", "out", "NB", "a")
    nb.split(splitter=["a", "NA.n"]).combine(combiner=["a", "NA.n"])

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    assert wf.nodes[0].result["out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.nodes[1].result["out"] == ({}, [2, 3, 4, 2, 3, 4, 5, 6])
    # output of the wf
    assert wf.result["NA_out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.result["NB_out"] == ({}, [2, 3, 4, 2, 3, 4, 5, 6])


@pytest.mark.skip("no exception")
@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_5b(change_dir, plugin):
    """wf with two nodes, the first one has a splitter and each element returns a list,
    the second takes elements of the list as an input - has a simple inner splitter
    and combiner that includes state splitter (and doesn't include inner splitter - Exception)
    """
    wf = Workflow(
        name="wf5b",
        workingdir="test_innerwf5b_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NB", "out", "NB_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    wf.add_nodes([na, nb])
    wf.connect("NA", "out", "NB", "a")
    nb.split(splitter=["a", "NA.n"]).combine(combiner=["NA.n"])

    with pytest.raises(Exception):
        sub = Submitter(runnable=wf, plugin=plugin)
        sub.run()
        sub.close()


# wf with multiple nodes and splitters that have more than one inner splitter


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_6(change_dir, plugin):
    """two nodes return lists, the third one have two inner inputs in scalar splitter"""
    wf = Workflow(
        name="wf6",
        workingdir="test_innerwf6_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NC", "out", "NC_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": 3},
    )
    nb = NodeBase(
        name="NB",
        interface=fun_list_generator_10(),
        workingdir="nb",
        output_names=["out"],
        inputs={"n": 3},
    )
    nc = NodeBase(
        name="NC",
        interface=fun_addvar(),
        workingdir="nc",
        output_names=["out"],
        splitter=("b", "c"),
        combiner=["b", "c"],
    )
    wf.add_nodes([na, nb, nc])
    wf.connect("NA", "out", "NC", "b")
    wf.connect("NB", "out", "NC", "c")

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    assert wf.nodes[0].result["out"] == ({}, [0, 1, 2])
    assert wf.nodes[1].result["out"] == ({}, [10, 11, 12])
    assert wf.nodes[2].result["out"] == ({}, [10, 12, 14])
    # output of the wf
    assert wf.result["NA_out"] == ({}, [0, 1, 2])
    assert wf.result["NC_out"] == ({}, [10, 12, 14])


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_6a(change_dir, plugin):
    """two nodes return lists, the third one have two inner inputs in outer splitter (Exception)
        TODO: should this actually raise an exception?
    """
    wf = Workflow(
        name="wf6a",
        workingdir="test_innerwf6a_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NC", "out", "NC_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": 3},
    )
    nb = NodeBase(
        name="NB",
        interface=fun_list_generator_10(),
        workingdir="nb",
        output_names=["out"],
        inputs={"n": 3},
    )
    nc = NodeBase(
        name="NC",
        interface=fun_addvar(),
        workingdir="nc",
        output_names=["out"],
        splitter=["b", "c"],
        combiner=["b", "c"],
    )
    wf.add_nodes([na, nb, nc])
    wf.connect("NA", "out", "NC", "b")
    wf.connect("NB", "out", "NC", "c")

    with pytest.raises(Exception):
        sub = Submitter(runnable=wf, plugin=plugin)
        sub.run()
        sub.close()


@pytest.mark.skip("don't know how to combine the inner splitter in NC...")
@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_7(change_dir, plugin):
    """two nodes return lists, the third one have two inner inputs in scalar splitter"""
    wf = Workflow(
        name="wf7",
        workingdir="test_innerwf7_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NC", "out", "NC_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nb = NodeBase(
        name="NB",
        interface=fun_list_generator_10(),
        workingdir="nb",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nc = NodeBase(
        name="NC",
        interface=fun_addvar(),
        workingdir="nc",
        output_names=["out"],
        splitter=("b", "c"),
        combiner=["b", "c"],
    )
    wf.add_nodes([na, nb, nc])
    wf.connect("NA", "out", "NC", "b")
    wf.connect("NB", "out", "NC", "c")

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    assert wf.nodes[0].result["out"] == ({}, [0, 1, 2])
    assert wf.nodes[1].result["out"] == ({}, [10, 11, 12])
    assert wf.nodes[2].result["out"] == ({}, [10, 12, 14])
    # output of the wf
    assert wf.result["NA_out"] == ({}, [0, 1, 2])
    assert wf.result["NC_out"] == ({}, [10, 12, 14])


# inner splitter is not combined in the same node


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_8(change_dir, plugin):
    """wf with two nodes, the first one returns a list,
    the second takes elements of the list as an input - has a simple inner splitter (NO combiner)
    """
    wf = Workflow(
        name="wf8",
        workingdir="test_innerwf8_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NB", "out", "NB_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": 3},
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    wf.add_nodes([na, nb])
    wf.connect("NA", "out", "NB", "a")
    nb.split(splitter="a")

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    # checking splitters/combiners
    assert wf.nodes[0].splitter is None
    assert wf.nodes[1].splitter == "NB.a"
    assert wf.nodes[1].state._inner_splitter == ["NB.a"]
    assert wf.nodes[1].state._splitter_wo_inner is None

    # checking results
    assert wf.nodes[0].result["out"] == ({}, [0, 1, 2])
    assert wf.nodes[1].result["out"] == [
        ({"NB.a": 0}, 2),
        ({"NB.a": 1}, 3),
        ({"NB.a": 2}, 4),
    ]
    # output of the wf
    assert wf.result["NA_out"] == ({}, [0, 1, 2])
    assert wf.result["NB_out"] == [({"NB.a": 0}, 2), ({"NB.a": 1}, 3), ({"NB.a": 2}, 4)]


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_9(change_dir, plugin):
    """wf with three nodes, the first one returns a list,
    the second takes elements of the list as an input - has a simple inner splitter,
     inner combiner is in the third node
    """
    wf = Workflow(
        name="wf9",
        workingdir="test_innerwf9_{}".format(plugin),
        wf_output_names=[("NA", "out", "NA_out"), ("NB", "out", "NB_out")],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": 3},
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    nc = NodeBase(
        name="NC", interface=fun_addtwo(), workingdir="nc", output_names=["out"]
    )
    wf.add_nodes([na, nb, nc])
    wf.connect("NA", "out", "NB", "a")
    wf.connect("NB", "out", "NC", "a")
    nb.split(splitter="a")
    nc.split(splitter="NB.a").combine(combiner="NB.a")

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    # checking splitters/combiners
    assert wf.nodes[0].splitter is None

    assert wf.nodes[1].splitter == "NB.a"
    assert wf.nodes[1].state._inner_splitter == ["NB.a"]
    assert wf.nodes[1].state._splitter_wo_inner is None
    assert wf.nodes[1].state._inner_splitter_comb == ["NB.a"]

    assert wf.nodes[2].splitter == "NB.a"
    assert wf.nodes[2].state._inner_splitter == ["NB.a"]
    assert wf.nodes[2].state._splitter_wo_inner is None
    assert wf.nodes[2].state._inner_splitter_comb == []
    assert wf.nodes[2].combiner == ["NB.a"]
    assert wf.nodes[2].state._inner_splitter == ["NB.a"]
    assert wf.nodes[2].state._combiner_wo_inner == []

    # checking results
    assert wf.nodes[0].result["out"] == ({}, [0, 1, 2])
    assert wf.nodes[1].result["out"] == [
        ({"NB.a": 0}, 2),
        ({"NB.a": 1}, 3),
        ({"NB.a": 2}, 4),
    ]
    assert wf.nodes[2].result["out"] == ({}, [4, 5, 6])
    # output of the wf
    assert wf.result["NA_out"] == ({}, [0, 1, 2])
    assert wf.result["NB_out"] == [({"NB.a": 0}, 2), ({"NB.a": 1}, 3), ({"NB.a": 2}, 4)]


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_10(change_dir, plugin):
    """wf with three nodes, the first one has a splitter and returns a list for each element,
    the second takes elements of the list as an input - has a simple inner splitter,
     inner combiner is in the third node
    """
    wf = Workflow(
        name="wf10",
        workingdir="test_innerwf10_{}".format(plugin),
        wf_output_names=[
            ("NA", "out", "NA_out"),
            ("NB", "out", "NB_out"),
            ("NC", "out", "NC_out"),
        ],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    nc = NodeBase(
        name="NC", interface=fun_addtwo(), workingdir="nc", output_names=["out"]
    )
    wf.add_nodes([na, nb, nc])
    wf.connect("NA", "out", "NB", "a")
    wf.connect("NB", "out", "NC", "a")
    nb.split(splitter=["NA.n", "a"])
    nc.split(splitter=["NA.n", "NB.a"]).combine(combiner="NB.a")

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    # checking splitters/combiners
    assert wf.nodes[0].splitter == "NA.n"

    assert wf.nodes[1].splitter == ["NA.n", "NB.a"]
    assert wf.nodes[1].state._inner_splitter == ["NB.a"]
    assert wf.nodes[1].state._splitter_wo_inner == "NA.n"
    assert wf.nodes[1].state._inner_splitter_comb == ["NB.a"]

    assert wf.nodes[2].splitter == ["NA.n", "NB.a"]
    assert wf.nodes[2].state._inner_splitter == ["NB.a"]
    assert wf.nodes[2].state._splitter_wo_inner == "NA.n"
    assert wf.nodes[2].state._inner_splitter_comb == []
    assert wf.nodes[2].combiner == ["NB.a"]
    assert wf.nodes[2].state._inner_splitter == ["NB.a"]
    assert wf.nodes[2].state._combiner_wo_inner == []

    # checking results
    assert wf.nodes[0].result["out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.nodes[1].result["out"] == [
        ({"NA.n": 3, "NB.a": 0}, 2),
        ({"NA.n": 3, "NB.a": 1}, 3),
        ({"NA.n": 3, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 0}, 2),
        ({"NA.n": 5, "NB.a": 1}, 3),
        ({"NA.n": 5, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 3}, 5),
        ({"NA.n": 5, "NB.a": 4}, 6),
    ]
    assert wf.nodes[2].result["out"] == [
        ({"NA.n": 3}, [4, 5, 6]),
        ({"NA.n": 5}, [4, 5, 6, 7, 8]),
    ]
    # output of the wf
    assert wf.result["NA_out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.result["NB_out"] == [
        ({"NA.n": 3, "NB.a": 0}, 2),
        ({"NA.n": 3, "NB.a": 1}, 3),
        ({"NA.n": 3, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 0}, 2),
        ({"NA.n": 5, "NB.a": 1}, 3),
        ({"NA.n": 5, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 3}, 5),
        ({"NA.n": 5, "NB.a": 4}, 6),
    ]
    assert wf.result["NC_out"] == [
        ({"NA.n": 3}, [4, 5, 6]),
        ({"NA.n": 5}, [4, 5, 6, 7, 8]),
    ]


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_10a(change_dir, plugin):
    """wf with three nodes, the first one has a splitter and returns a list for each elemnt,
    the second takes elements of the list as an input - has a simple inner splitter,
     inner combiner and normal combiner are in the third node
    """
    wf = Workflow(
        name="wf10a",
        workingdir="test_innerwf10a_{}".format(plugin),
        wf_output_names=[
            ("NA", "out", "NA_out"),
            ("NB", "out", "NB_out"),
            ("NC", "out", "NC_out"),
        ],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    nc = NodeBase(
        name="NC", interface=fun_addtwo(), workingdir="nc", output_names=["out"]
    )
    wf.add_nodes([na, nb, nc])
    wf.connect("NA", "out", "NB", "a")
    wf.connect("NB", "out", "NC", "a")
    nb.split(splitter=["NA.n", "a"])
    nc.split(splitter=["NA.n", "NB.a"]).combine(combiner=["NB.a", "NA.n"])

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    # checking splitters/combiners
    assert wf.nodes[0].splitter == "NA.n"

    assert wf.nodes[1].splitter == ["NA.n", "NB.a"]
    assert wf.nodes[1].state._inner_splitter == ["NB.a"]
    assert wf.nodes[1].state._splitter_wo_inner == "NA.n"
    assert wf.nodes[1].state._inner_splitter_comb == ["NB.a"]

    assert wf.nodes[2].splitter == ["NA.n", "NB.a"]
    assert wf.nodes[2].state._inner_splitter == ["NB.a"]
    assert wf.nodes[2].state._splitter_wo_inner == "NA.n"
    assert wf.nodes[2].state._inner_splitter_comb == []
    assert wf.nodes[2].combiner == ["NB.a", "NA.n"]
    assert wf.nodes[2].state._inner_splitter == ["NB.a"]
    assert wf.nodes[2].state._combiner_wo_inner == ["NA.n"]

    # checking results
    assert wf.nodes[0].result["out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.nodes[1].result["out"] == [
        ({"NA.n": 3, "NB.a": 0}, 2),
        ({"NA.n": 3, "NB.a": 1}, 3),
        ({"NA.n": 3, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 0}, 2),
        ({"NA.n": 5, "NB.a": 1}, 3),
        ({"NA.n": 5, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 3}, 5),
        ({"NA.n": 5, "NB.a": 4}, 6),
    ]
    assert wf.nodes[2].result["out"] == ({}, [4, 5, 6, 4, 5, 6, 7, 8])
    # output of the wf
    assert wf.result["NA_out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.result["NB_out"] == [
        ({"NA.n": 3, "NB.a": 0}, 2),
        ({"NA.n": 3, "NB.a": 1}, 3),
        ({"NA.n": 3, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 0}, 2),
        ({"NA.n": 5, "NB.a": 1}, 3),
        ({"NA.n": 5, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 3}, 5),
        ({"NA.n": 5, "NB.a": 4}, 6),
    ]
    assert wf.result["NC_out"] == ({}, [4, 5, 6, 4, 5, 6, 7, 8])


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_10b(change_dir, plugin):
    """wf with three nodes, the first one has a splitter and returns a list for each elemnt,
    the second takes elements of the list as an input - has a simple inner splitter,
     inner combiner and normal combiner are in the third node
     the same as 10a, just with different order of combiner
    """
    wf = Workflow(
        name="wf10b",
        workingdir="test_innerwf10b_{}".format(plugin),
        wf_output_names=[
            ("NA", "out", "NA_out"),
            ("NB", "out", "NB_out"),
            ("NC", "out", "NC_out"),
        ],
    )
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    nc = NodeBase(
        name="NC", interface=fun_addtwo(), workingdir="nc", output_names=["out"]
    )
    wf.add_nodes([na, nb, nc])
    wf.connect("NA", "out", "NB", "a")
    wf.connect("NB", "out", "NC", "a")
    nb.split(splitter=["NA.n", "a"])
    nc.split(splitter=["NA.n", "NB.a"]).combine(combiner=["NA.n", "NB.a"])

    sub = Submitter(runnable=wf, plugin=plugin)
    sub.run()
    sub.close()

    assert wf.nodes[0].result["out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.nodes[1].result["out"] == [
        ({"NA.n": 3, "NB.a": 0}, 2),
        ({"NA.n": 3, "NB.a": 1}, 3),
        ({"NA.n": 3, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 0}, 2),
        ({"NA.n": 5, "NB.a": 1}, 3),
        ({"NA.n": 5, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 3}, 5),
        ({"NA.n": 5, "NB.a": 4}, 6),
    ]
    assert wf.nodes[2].result["out"] == ({}, [4, 5, 6, 4, 5, 6, 7, 8])
    # output of the wf
    assert wf.result["NA_out"] == [
        ({"NA.n": 3}, [0, 1, 2]),
        ({"NA.n": 5}, [0, 1, 2, 3, 4]),
    ]
    assert wf.result["NB_out"] == [
        ({"NA.n": 3, "NB.a": 0}, 2),
        ({"NA.n": 3, "NB.a": 1}, 3),
        ({"NA.n": 3, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 0}, 2),
        ({"NA.n": 5, "NB.a": 1}, 3),
        ({"NA.n": 5, "NB.a": 2}, 4),
        ({"NA.n": 5, "NB.a": 3}, 5),
        ({"NA.n": 5, "NB.a": 4}, 6),
    ]
    assert wf.result["NC_out"] == ({}, [4, 5, 6, 4, 5, 6, 7, 8])


@pytest.mark.parametrize("plugin", Plugins)
@python35_only
def test_innerwf_10c(change_dir, plugin):
    """wf with three nodes, the first one has a splitter and returns a list for each elemnt,
    the second takes elements of the list as an input - has a simple inner splitter,
    normal combiner is in the third node (should raise an error since inner splitter is not combined)
    """
    wf = Workflow(name="wf10c", workingdir="test_innerwf10c_{}".format(plugin))
    na = NodeBase(
        name="NA",
        interface=fun_list_generator(),
        workingdir="na",
        output_names=["out"],
        inputs={"n": [3, 5]},
        splitter="n",
    )
    nb = NodeBase(
        name="NB", interface=fun_addtwo(), workingdir="nb", output_names=["out"]
    )
    nc = NodeBase(
        name="NC", interface=fun_addtwo(), workingdir="nc", output_names=["out"]
    )
    wf.add_nodes([na, nb, nc])
    wf.connect("NA", "out", "NB", "a")
    wf.connect("NB", "out", "NC", "a")
    nb.split(splitter=["NA.n", "a"])
    nc.split(splitter=["NA.n", "NB.a"]).combine(combiner="NA.n")

    with pytest.raises(Exception):
        sub = Submitter(runnable=wf, plugin=plugin)
        sub.run()
        sub.close()
