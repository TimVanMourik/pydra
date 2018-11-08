"""Basic compute graph elements"""
import os
import itertools
import pdb
import networkx as nx
import numpy as np
from collections import OrderedDict

from nipype.utils.filemanip import loadpkl
from nipype import logging, Function

from . import state
from . import auxiliary as aux
logger = logging.getLogger('nipype.workflow')


class NodeBase(object):
    def __init__(self, name, mapper=None, combiner=None, inputs=None,
                 other_mappers=None, write_state=True, *args, **kwargs):
        """A base structure for nodes in the computational graph (i.e. both
        ``Node`` and ``Workflow``).

        Parameters
        ----------

        name : str
            Unique name of this node
        mapper : str or (list or tuple of (str or mappers))
            Whether inputs should be mapped at run time
        combiner: str or list of strings (names of variables)
            variables that should be used to combine results together
        inputs : dictionary (input name, input value or list of values)
            States this node's input names
        other_mappers : dictionary (name of a node, mapper of the node)
            information about other nodes' mappers from workflow (in case the mapper
            from previous node is used)
        write_state : True
            flag that says if value of state input should be written out to output
            and directories (otherwise indices are used)



        """
        self.name = name
        self._inputs = {}
        self._state_inputs = {}

        if inputs:
            self.inputs = inputs

        if mapper:
            # adding name of the node to the input name within the mapper
            mapper = aux.change_mapper(mapper, self.name)
        self._mapper = mapper
        if other_mappers:
            self._other_mappers = other_mappers
        else:
            self._other_mappers = {}
        self._combiner = None
        if combiner:
            self.combiner = combiner
        self._state = state.State(mapper=self._mapper, node_name=self.name, other_mappers=self._other_mappers,
                                  combiner=self.combiner)
        self._output = {}
        self._result = {}
        # flag that says if the node/wf is ready to run (has all input)
        self.ready2run = True
        # needed outputs from other nodes if the node part of a wf
        self.needed_outputs = []
        # flag that says if node finished all jobs
        self._is_complete = False
        self.write_state = write_state



    @property
    def state(self):
        return self._state

    @property
    def mapper(self):
        return self._mapper

    @mapper.setter
    def mapper(self, mapper):
        if self._mapper:
            raise Exception("mapper is already set")
        self._mapper = aux.change_mapper(mapper, self.name)
        # updating state
        self._state = state.State(mapper=self._mapper, node_name=self.name, combiner=self.combiner,
                                  other_mappers=self._other_mappers)

    @property
    def combiner(self):
        return self._combiner

    @combiner.setter
    def combiner(self, combiner):
        if self._combiner:
            raise Exception("combiner is already set")
        if not self.mapper:
            raise Exception("mapper has to be set before setting combiner")
        if type(combiner) is str:
            combiner = [combiner]
        elif type(combiner) is not list:
            raise Exception("combiner should be a string or a list")
        self._combiner = aux.change_mapper(combiner, self.name)
        if hasattr(self, "state"):
            self.state.combiner = self._combiner
        for el in self._combiner:
            if not aux.search_mapper(el, self.mapper):
                raise Exception("element {} of combiner is not found in the mapper {}".format(
                    el, self.mapper))

    @property
    def inputs(self):
        return self._inputs

    @inputs.setter
    def inputs(self, inputs):
        # Massage inputs dict
        inputs = {
            ".".join((self.name, key)): value if not isinstance(value, list) else np.array(value)
            for key, value in inputs.items()
        }
        self._inputs.update(inputs)
        self._state_inputs.update(inputs)

    @property
    def state_inputs(self):
        return self._state_inputs

    @state_inputs.setter
    def state_inputs(self, state_inputs):
        self._state_inputs.update(state_inputs)

    @property
    def output(self):
        return self._output

    @property
    def result(self):
        if not self._result:
            self._reading_results()
        return self._result

    def prepare_state_input(self):
        self._state.prepare_state_input(state_inputs=self.state_inputs)


    def map(self, mapper, inputs=None):
        self.mapper = mapper
        if inputs:
            self.inputs = inputs
            self._state_inputs.update(self.inputs)
        return self


    def combine(self, combiner):
        self.combiner = combiner
        return self


    def checking_input_el(self, ind):
        """checking if all inputs are available (for specific state element)"""
        try:
            self.get_input_el(ind)
            return True
        except:  #TODO specify
            return False

    # dj: this is not used for a single node
    def get_input_el(self, ind):
        """collecting all inputs required to run the node (for specific state element)"""
        state_dict = self.state.state_values(ind)
        inputs_dict = {k: state_dict[k] for k in self._inputs.keys()}
        if not self.write_state:
            state_dict = self.state.state_ind(ind)
        # reading extra inputs that come from previous nodes
        for (from_node, from_socket, to_socket) in self.needed_outputs:
            # if the previous node has combiner I have to collect all elements
            if from_node.state.combiner:
                inputs_dict["{}.{}".format(self.name, to_socket)] =\
                    self._get_input_comb(from_node, from_socket, state_dict)
            else:
                dir_nm_el_from, _ = from_node._directory_name_state_surv(state_dict)
                # TODO: do I need this if, what if this is wf?
                if is_node(from_node):
                    out_from = self._reading_ci_output(
                        node=from_node, dir_nm_el=dir_nm_el_from, out_nm=from_socket)
                    if out_from:
                        inputs_dict["{}.{}".format(self.name, to_socket)] = out_from
                    else:
                        raise Exception("output from {} doesnt exist".format(from_node))
        return state_dict, inputs_dict


    def _get_input_comb(self, from_node, from_socket, state_dict):
        """collecting all outputs from previous node that has combiner"""
        state_dict_all = self._state_dict_all_comb(from_node, state_dict)
        inputs_all = []
        for state in state_dict_all:
            dir_nm_el_from = "_".join([
                "{}:{}".format(i, j) for i, j in list(state.items())])
            if is_node(from_node):
                out_from = self._reading_ci_output(
                    node=from_node, dir_nm_el=dir_nm_el_from, out_nm=from_socket)
                if out_from:
                    inputs_all.append(out_from)
                else:
                    raise Exception("output from {} doesnt exist".format(from_node))
        return inputs_all



    def _state_dict_all_comb(self, from_node, state_dict):
        """collecting state dictionary for all elements that were combined together"""
        elements_per_axes = {}
        axis_for_input = {}
        all_axes = []
        for inp in from_node.combiner:
            axis_for_input[inp] = from_node.state._axis_for_input[inp]
            for (i, ax)  in enumerate(axis_for_input[inp]):
                elements_per_axes[ax] = state_dict[inp].shape[i]
                all_axes.append(ax)
        all_axes = list(set(all_axes))
        all_axes.sort()
        shape = [el for (ax, el) in sorted(elements_per_axes.items())]
        all_elements = [range(i) for i in shape]
        index_generator = itertools.product(*all_elements)
        state_dict_all = []
        for ind in index_generator:
            state_dict_all.append(self._state_dict_el_for_comb(ind, state_dict,
                                                               axis_for_input))
        return state_dict_all


    # similar to State.stae_value (could be combined?)
    def _state_dict_el_for_comb(self, ind, state_inputs, axis_for_input, value=True):
        """state input for a specific ind (used for connection)"""
        state_dict_el = {}
        for input, ax in axis_for_input.items():
            # checking which axes are important for the input
            sl_ax = slice(ax[0], ax[-1] + 1)
            # taking the indexes for the axes
            ind_inp = tuple(ind[sl_ax])  # used to be list
            if value:
                state_dict_el[input] = state_inputs[input][ind_inp]
            else:  # using index instead of value
                ind_inp_str = "x".join([str(el) for el in ind_inp])
                state_dict_el[input] = ind_inp_str
        # adding values from input that are not used in the mapper
        for input in set(state_inputs) - set(axis_for_input):
            if value:
                state_dict_el[input] = state_inputs[input]
            else:
                state_dict_el[input] = None
        # in py3.7 we can skip OrderedDict
        return OrderedDict(sorted(state_dict_el.items(), key=lambda t: t[0]))


    def _reading_ci_output(self, dir_nm_el, out_nm, node=None):
        """used for current interfaces: checking if the output exists and returns the path if it does"""
        if not node:
            node = self
        result_pklfile = os.path.join(os.getcwd(), node.workingdir, dir_nm_el,
                                      node.interface.nn.name, "result_{}.pklz".format(
                                          node.interface.nn.name))
        if os.path.exists(result_pklfile) and os.stat(result_pklfile).st_size > 0:
            out = getattr(loadpkl(result_pklfile).outputs, out_nm)
            if out:
                return out
        return False


    # TODO: this is used now only for node, it probbably should be also for wf
    def _directory_name_state_surv(self, state_dict):
        """eliminating all inputs from state dictionary that are not in
        the mapper anymore (e.g. because of the combiner);
        create name of the dictionary
        """
        state_surv_dict = dict((key, val) for (key, val) in state_dict.items()
                               if key in self.state._mapper_rpn)
        dir_nm_el = "_".join(["{}:{}".format(i, j)
                              for i, j in list(state_surv_dict.items())])
        if not self.mapper:
            dir_nm_el = ""
        return dir_nm_el, state_surv_dict


    # checking if all outputs are saved
    @property
    def is_complete(self):
        # once _is_complete os True, this should not change
        logger.debug('is_complete {}'.format(self._is_complete))
        if self._is_complete:
            return self._is_complete
        else:
            return self._check_all_results()

    def get_output(self):
        raise NotImplementedError

    def _check_all_results(self):
        raise NotImplementedError

    def _reading_results(self):
        raise NotImplementedError

    def _dict_tuple2list(self, container, key=False):
        if type(container) is dict:
            if key:
                val_l = [(key, val) for (key, val) in container.items()]
            else:
                val_l = [val for (_, val) in container.items()]
        elif type(container) is tuple:
            val_l = [container]
        else:
            raise Exception("{} has to be dict or tuple".format(container))
        return val_l


class Node(NodeBase):
    def __init__(self, name, interface, inputs=None, mapper=None, workingdir=None,
                 other_mappers=None, output_names=None, write_state=True,
                 combiner=None, *args, **kwargs):
        super(Node, self).__init__(name=name, mapper=mapper, inputs=inputs,
                                   other_mappers=other_mappers, write_state=write_state,
                                   combiner=combiner, *args, **kwargs)

        # working directory for node, will be change if node is a part of a wf
        self.workingdir = workingdir
        self.interface = interface

        # list of  interf_key_out
        self.output_names = output_names
        if not self.output_names:
            self.output_names = []

    # dj: not sure if I need it
    # def __deepcopy__(self, memo): # memo is a dict of id's to copies
    #     id_self = id(self)        # memoization avoids unnecesary recursion
    #     _copy = memo.get(id_self)
    #     if _copy is None:
    #         # changing names of inputs and input_map, so it doesnt contain node.name
    #         inputs_copy = dict((key[len(self.name)+1:], deepcopy(value))
    #                            for (key, value) in self.inputs.items())
    #         interface_copy = deepcopy(self.interface)
    #         interface_copy.input_map = dict((key, val[len(self.name)+1:])
    #                                         for (key, val) in interface_copy.input_map.items())
    #         _copy = type(self)(
    #             name=deepcopy(self.name), interface=interface_copy,
    #             inputs=inputs_copy, mapper=deepcopy(self.mapper),
    #             base_dir=deepcopy(self.nodedir), other_mappers=deepcopy(self._other_mappers))
    #         memo[id_self] = _copy
    #     return _copy

    def run_interface_el(self, i, ind):
        """ running interface one element generated from node_state."""
        logger.debug("Run interface el, name={}, i={}, ind={}".format(self.name, i, ind))
        state_dict, inputs_dict = self.get_input_el(ind)
        if not self.write_state:
            state_dict = self.state.state_ind(ind)
        dir_nm_el, state_surv_dict = self._directory_name_state_surv(state_dict)
        print("Run interface el, dict={}".format(state_surv_dict))
        logger.debug("Run interface el, name={}, inputs_dict={}, state_dict={}".format(
            self.name, inputs_dict, state_surv_dict))
        res = self.interface.run(
            inputs=inputs_dict,
            base_dir=os.path.join(os.getcwd(), self.workingdir),
            dir_nm_el=dir_nm_el)
        return res


    def get_output(self):
        """collecting all outputs and updating self._output"""
        for key_out in self.output_names:
            self._output[key_out] = {}
            for (i, ind) in enumerate(itertools.product(*self.state.all_elements)):
                if self.write_state:
                    state_dict = self.state.state_values(ind)
                else:
                    state_dict = self.state.state_ind(ind)
                dir_nm_el, state_surv_dict = self._directory_name_state_surv(state_dict)
                if self.mapper:
                    output_el = (state_surv_dict, self._reading_ci_output(dir_nm_el,
                                                                     out_nm=key_out))
                    if not self.combiner: # only mapper
                        self._output[key_out][dir_nm_el] = output_el
                    else: #assuming that only combined output is saved
                        self._combined_output(key_out, state_dict, output_el)
                else:
                    self._output[key_out] = \
                        (state_surv_dict, self._reading_ci_output(dir_nm_el, out_nm=key_out))
        return self._output


    def _combined_output(self, key_out, state_dict, output_el):
        dir_nm_comb = "_".join(["{}:{}".format(i, j)
                                for i, j in list(state_dict.items())
                                if i not in self.state.inp_to_remove])
        if dir_nm_comb in self._output[key_out].keys():
            self._output[key_out][dir_nm_comb].append(output_el)
        else:
            self._output[key_out][dir_nm_comb] = [output_el]


    def _check_all_results(self):
        """checking if all files that should be created are present"""
        for ind in itertools.product(*self.state.all_elements):
            if self.write_state:
                state_dict = self.state.state_values(ind)
            else:
                state_dict = self.state.state_ind(ind)
            dir_nm_el, _ = self._directory_name_state_surv(state_dict)
            for key_out in self.output_names:
                if not self._reading_ci_output(dir_nm_el, key_out):
                    return False
        self._is_complete = True
        return True


    def _reading_results(self):
        """temporary: reading results from output files (that is now just txt)
            should be probably just reading output for self.output_names
        """
        for key_out in self.output_names:
            #self._result[key_out] = []
            if self._state_inputs:
                # TODO: should I remember state (both with ain w/o combiner)
                if not self.combiner:
                    val_l = self._dict_tuple2list(self._output[key_out])
                    #for (st_dict, out) in val_l:
                    self._result[key_out] = val_l
                else:
                    val_l = self._dict_tuple2list(self._output[key_out], key=True)
                    self._result[key_out] = val_l
                    #for val in val_l:

            else:
                # st_dict should be {}
                # not sure if this is used (not tested)
                (st_dict, out) = self._output[key_out][None]
                self._result[key_out].append(({}, out))

    # dj: removing temp. from Node class
    # def run(self, plugin="serial"):
    #     """preparing the node to run and run the interface"""
    #     self.prepare_state_input()
    #     submitter = sub.SubmitterNode(plugin, node=self)
    #     submitter.run_node()
    #     submitter.close()
    #     self.collecting_output()


class Workflow(NodeBase):
    def __init__(self, name, inputs=None, wf_output_names=None, mapper=None,
                 nodes=None, workingdir=None, write_state=True, *args, **kwargs):
        super(Workflow, self).__init__(name=name, mapper=mapper, inputs=inputs,
                                       write_state=write_state, *args, **kwargs)

        self.graph = nx.DiGraph()
        # all nodes in the workflow (probably will be removed)
        self._nodes = []
        # saving all connection between nodes
        self.connected_var = {}
        # input that are expected by nodes to get from wf.inputs
        self.needed_inp_wf = []
        if nodes:
            self.add_nodes(nodes)
        for nn in self._nodes:
            self.connected_var[nn] = {}
        # key: name of a node, value: the node
        self._node_names = {}
        # key: name of a node, value: mapper of the node
        self._node_mappers = {}
        # dj: not sure if this should be different than base_dir
        self.workingdir = os.path.join(os.getcwd(), workingdir)
        # list of (nodename, output name in the name, output name in wf) or (nodename, output name in the name)
        # dj: using different name than for node, since this one it is defined by a user
        self.wf_output_names = wf_output_names

        # nodes that are created when the workflow has mapper (key: node name, value: list of nodes)
        self.inner_nodes = {}
        # in case of inner workflow this points to the main/parent workflow
        self.parent_wf = None
        # dj not sure what was the motivation, wf_klasses gives an empty list
        #mro = self.__class__.mro()
        #wf_klasses = mro[:mro.index(Workflow)][::-1]
        #items = {}
        #for klass in wf_klasses:
        #    items.update(klass.__dict__)
        #for name, runnable in items.items():
        #    if name in ('__module__', '__doc__'):
        #        continue

        #    self.add(name, value)

    @property
    def nodes(self):
        return self._nodes

    @property
    def graph_sorted(self):
        # TODO: should I always update the graph?
        return list(nx.topological_sort(self.graph))

    def map_node(self, mapper, node=None, inputs=None):
        """this is setting a mapper to the wf's nodes (not to the wf)"""
        if type(node) is str:
            node = self._node_names[node]
        elif node is None:
            node = self._last_added
        if node.mapper:
            raise Exception("Cannot assign two mappings to the same input")
        node.map(mapper=mapper, inputs=inputs)
        if node.combiner:
            self._node_mappers[node.name] = node.state.mapper_comb
        else:
            self._node_mappers[node.name] = node.mapper


    def get_output(self):
        # not sure, if I should collecto output of all nodes or only the ones that are used in wf.output
        self.node_outputs = {}
        for nn in self.graph:
            if self.mapper:
                self.node_outputs[nn.name] = [ni.get_output() for ni in self.inner_nodes[nn.name]]
            else:
                self.node_outputs[nn.name] = nn.get_output()
        if self.wf_output_names:
            for out in self.wf_output_names:
                if len(out) == 2:
                    node_nm, out_nd_nm, out_wf_nm = out[0], out[1], out[1]
                elif len(out) == 3:
                    node_nm, out_nd_nm, out_wf_nm = out
                else:
                    raise Exception("wf_output_names should have 2 or 3 elements")
                if out_wf_nm not in self._output.keys():
                    if self.mapper:
                        self._output[out_wf_nm] = {}
                        for (i, ind) in enumerate(itertools.product(*self.state.all_elements)):
                            if self.write_state:
                                wf_inputs_dict = self.state.state_values(ind)
                            else:
                                wf_inputs_dict = self.state.state_ind(ind)
                            dir_nm_el, _ = self._directory_name_state_surv(wf_inputs_dict)
                            self._output[out_wf_nm][dir_nm_el] = self.node_outputs[node_nm][i][
                                out_nd_nm]
                    else:
                        self._output[out_wf_nm] = self.node_outputs[node_nm][out_nd_nm]
                else:
                    raise Exception(
                        "the key {} is already used in workflow.result".format(out_wf_nm))
        return self._output


    # TODO: might merge with the function from Node
    def _check_all_results(self):
        """checking if all files that should be created are present"""
        for nn in self.graph_sorted:
            if nn.name in self.inner_nodes.keys():
                if not all([ni.is_complete for ni in self.inner_nodes[nn.name]]):
                    return False
            else:
                if not nn.is_complete:
                    return False
        self._is_complete = True
        return True

    # TODO: should try to merge with the function from Node
    def _reading_results(self):
        """reading all results of the workflow
           using temporary Node._reading_results that reads txt files
        """
        if self.wf_output_names:
            for out in self.wf_output_names:
                key_out = out[2] if len(out) == 3 else out[1]
                self._result[key_out] = []
                if self.mapper:
                    for (i, ind) in enumerate(itertools.product(*self.state.all_elements)):
                        if self.write_state:
                            wf_inputs_dict = self.state.state_values(ind)
                        else:
                            wf_inputs_dict = self.state.state_ind(ind)
                        dir_nm_el, _ = self._directory_name_state_surv(wf_inputs_dict)
                        res_l = []
                        val_l = self._dict_tuple2list(self.output[key_out][dir_nm_el])
                        for val in val_l:
                            res_l.append(val)
                        self._result[key_out].append((wf_inputs_dict, res_l))
                else:
                    val_l = self._dict_tuple2list(self.output[key_out])
                    for val in val_l:
                        self._result[key_out].append(val)


    # TODO: this should be probably using add method
    def add_nodes(self, nodes):
        """adding nodes without defining connections
            most likely it will be removed at the end
        """
        self.graph.add_nodes_from(nodes)
        for nn in nodes:
            self._nodes.append(nn)
            #self._inputs.update(nn.inputs)
            self.connected_var[nn] = {}
            self._node_names[nn.name] = nn
            # when we have a combiner in a previous node, we have to pass the final mapper
            if nn.combiner:
                self._node_mappers[nn.name] = nn.state.mapper_comb
            else:
                self._node_mappers[nn.name] = nn.mapper
            nn.other_mappers = self._node_mappers


    # TODO: workingir shouldn't have None
    def add(self, runnable, name=None, workingdir=None, inputs=None, input_names=None,
            output_names=None, mapper=None, combiner=None, write_state=True, **kwargs):
        if is_function(runnable):
            if not output_names:
                output_names = ["out"]
            if input_names is None:
                raise Exception("you need to specify input_names")
            if not name:
                raise Exception("you have to specify name for the node")
            nipype1_interf = Function(function=runnable, input_names=input_names,
                                      output_names=output_names)
            interface = aux.CurrentInterface(interface=nipype1_interf, name="addtwo")
            if not workingdir:
                workingdir = name
            node = Node(interface=interface, workingdir=workingdir, name=name,
                        inputs=inputs, mapper=mapper, other_mappers=self._node_mappers,
                        combiner=combiner, output_names=output_names,
                        write_state=write_state)
        elif is_current_interface(runnable):
            if not name:
                raise Exception("you have to specify name for the node")
            if not workingdir:
                workingdir = name
            node = Node(interface=runnable, workingdir=workingdir, name=name,
                        inputs=inputs, mapper=mapper, other_mappers=self._node_mappers,
                        combiner=combiner, output_names=output_names,
                        write_state=write_state)
        elif is_nipype_interface(runnable):
            ci = aux.CurrentInterface(interface=runnable, name=name)
            if not name:
                raise Exception("you have to specify name for the node")
            if not workingdir:
                workingdir = name
            node = Node(interface=ci, workingdir=workingdir, name=name, inputs=inputs,
                        mapper=mapper, other_mappers=self._node_mappers,
                        combiner=combiner, output_names=output_names,
                        write_state=write_state)
        elif is_node(runnable):
            node = runnable
            node.other_mappers = self._node_mappers
        elif is_workflow(runnable):
            node = runnable
        else:
            raise ValueError("Unknown workflow element: {!r}".format(runnable))
        self.add_nodes([node])
        self._last_added = node
        # connecting inputs to other nodes outputs
        for (inp, source) in kwargs.items():
            try:
                from_node_nm, from_socket = source.split(".")
                self.connect(from_node_nm, from_socket, node.name, inp)
            # TODO not sure if i need it, just check if from_node_nm is not None??
            except (ValueError):
                self.connect_wf_input(source, node.name, inp)
        return self

    def connect(self, from_node_nm, from_socket, to_node_nm, to_socket):
        from_node = self._node_names[from_node_nm]
        to_node = self._node_names[to_node_nm]
        self.graph.add_edges_from([(from_node, to_node)])
        if not to_node in self.nodes:
            self.add_nodes(to_node)
        self.connected_var[to_node][to_socket] = (from_node, from_socket)
        # from_node.sending_output.append((from_socket, to_node, to_socket))
        logger.debug('connecting {} and {}'.format(from_node, to_node))

    def connect_wf_input(self, inp_wf, node_nm, inp_nd):
        self.needed_inp_wf.append((node_nm, inp_wf, inp_nd))

    def preparing(self, wf_inputs=None, wf_inputs_ind=None, st_inputs=None):
        """preparing nodes which are connected: setting the final mapper and state_inputs"""
        #pdb.set_trace()
        for node_nm, inp_wf, inp_nd in self.needed_inp_wf:
            node = self._node_names[node_nm]
            if "{}.{}".format(self.name, inp_wf) in wf_inputs:
                node.state_inputs.update({
                    "{}.{}".format(node_nm, inp_nd):
                    wf_inputs["{}.{}".format(self.name, inp_wf)]
                })
                node.inputs.update({
                    "{}.{}".format(node_nm, inp_nd):
                    wf_inputs["{}.{}".format(self.name, inp_wf)]
                })
            else:
                raise Exception("{}.{} not in the workflow inputs".format(self.name, inp_wf))
        for nn in self.graph_sorted:
            if self.write_state:
                if not st_inputs: st_inputs=wf_inputs
                dir_nm_el, _ = self._directory_name_state_surv(st_inputs)
            else:
                # wf_inputs_ind is already ok, doesn't need st_inputs_ind
                  dir_nm_el, _ = self._directory_name_state_surv(wf_inputs_ind)
            if not self.mapper:
                dir_nm_el = ""
            nn.workingdir = os.path.join(self.workingdir, dir_nm_el, nn.name)
            nn._is_complete = False  # helps when mp is used
            try:
                for inp, (out_node, out_var) in self.connected_var[nn].items():
                    nn.ready2run = False  #it has some history (doesnt have to be in the loop)
                    nn.state_inputs.update(out_node.state_inputs)
                    nn.needed_outputs.append((out_node, out_var, inp))
                    #if there is no mapper provided, i'm assuming that mapper is taken from the previous node
                    if (not nn.mapper or nn.mapper == out_node.mapper) and out_node.mapper:
                        if out_node.combiner:
                            nn.mapper = out_node.state.mapper_comb
                        else:
                            nn.mapper = out_node.mapper
                    else:
                        pass
                    #TODO: implement inner mapper
            except (KeyError):
                # tmp: we don't care about nn that are not in self.connected_var
                pass
            nn.prepare_state_input()

    # removing temp. from Workflow
    # def run(self, plugin="serial"):
    #     #self.preparing(wf_inputs=self.inputs) # moved to submitter
    #     self.prepare_state_input()
    #     logger.debug('the sorted graph is: {}'.format(self.graph_sorted))
    #     submitter = sub.SubmitterWorkflow(workflow=self, plugin=plugin)
    #     submitter.run_workflow()
    #     submitter.close()
    #     self.collecting_output()


def is_function(obj):
    return hasattr(obj, '__call__')


def is_current_interface(obj):
    return type(obj) is aux.CurrentInterface


def is_nipype_interface(obj):
    return hasattr(obj, "_run_interface")


def is_node(obj):
    return type(obj) is Node


def is_workflow(obj):
    return type(obj) is Workflow
