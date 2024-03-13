# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# This work is a modification of Qiskit's DAGCircuit class.

import rustworkx as rx
from collections import OrderedDict, defaultdict, deque, namedtuple
from typing import Dict, Generator, Any, List
from qiskit.circuit.quantumregister import QuantumRegister, Qubit

from qiskit.circuit.classicalregister import ClassicalRegister, Clbit
from sabre_dag_experiments.bidag_op_node import DAGNode, DAGOpNode, DAGInNode, DAGOutNode
from qiskit.circuit.bit import Bit


BitLocations = namedtuple("BitLocations", ("index", "registers"))

class BidirectionalDAGCircuit:
    
    def __init__(self):
        """Create an empty circuit."""

        # Circuit name.  Generally, this corresponds to the name
        # of the QuantumCircuit from which the DAG was generated.
        self.name = None

        # Circuit metadata
        self.metadata = {}

        # Cache of dag op node sort keys
        self._key_cache = {}

        # Set of wires (Register,idx) in the dag
        self._wires = set()

        # Map from wire (Register,idx) to input nodes of the graph
        self.input_map = OrderedDict()

        # Map from wire (Register,idx) to output nodes of the graph
        self.output_map_left = OrderedDict()
        self.output_map_right = OrderedDict()

        # Directed multigraph whose nodes are inputs, outputs, or operations.
        # Operation nodes have equal in- and out-degrees and carry
        # additional data about the operation, including the argument order
        # and parameter values.
        # Input nodes have out-degree 1 and output nodes have in-degree 1.
        # Edges carry wire labels (reg,idx) and each operation has
        # corresponding in- and out-edges with the same wire labels.
        self._multi_graph = rx.PyDAG()

        # Map of qreg/creg name to Register object.
        self.qregs = OrderedDict()
        self.cregs = OrderedDict() # must remain here in order for draw() to work

        # List of Qubit/Clbit wires that the DAG acts on.
        self.qubits: List[Qubit] = []
        self.clbits: List[Clbit] = []

        # Dictionary mapping of Qubit and Clbit instances to a tuple comprised of
        # 0) corresponding index in dag.{qubits,clbits} and
        # 1) a list of Register-int pairs for each Register containing the Bit and
        # its index within that register.
        self._qubit_indices: Dict[Qubit, BitLocations] = {}
        self._clbit_indices: Dict[Clbit, BitLocations] = {}

        self._op_names = {}

        self.duration = None
        self._global_phase = 0
        self._calibrations = defaultdict(dict)
        self.unit = "dt"

    def num_qubits(self):
        """Return the total number of qubits used by the circuit.
        num_qubits() replaces former use of width().
        DAGCircuit.width() now returns qubits + clbits for
        consistency with Circuit.width() [qiskit-terra #2564].
        """
        return len(self.qubits)
    
    # START: GETTERS AND SETTERS TO MAKE CLASS COMPATIBLE WITH QISKIT'S SABRELAYOUT PASS AND QISKIT'S CONVERTERS

    @property
    def global_phase(self):
        """Return the global phase of the circuit."""
        return self._global_phase
    
    def num_clbits(self):
        """Return the total number of classical bits used by the circuit."""
        return len(self.clbits) # should be zero
    
    @property
    def calibrations(self):
        """Return calibration dictionary.

        The custom pulse definition of a given gate is of the form
            {'gate_name': {(qubits, params): schedule}}
        """
        return dict(self._calibrations)
    
    # END: GETTERS AND SETTERS TO MAKE CLASS COMPATIBLE WITH QISKIT'S SABRELAYOUT PASS
    
    def topological_op_nodes(self, key=None) -> Generator[DAGOpNode, Any, Any]:
        """
        Yield op nodes in topological order.

        Allowed to pass in specific key to break ties in top order

        Args:
            key (Callable): A callable which will take a DAGNode object and
                return a string sort key. If not specified the
                :attr:`~qiskit.dagcircuit.DAGNode.sort_key` attribute will be
                used as the sort key for each node.

        Returns:
            generator(DAGOpNode): op node in topological order
        """
        # print('topological ordering of bidirectional DAGCircuit')
        # for nd in self.topological_nodes(key):
        #     if isinstance(nd, DAGOpNode):
        #         print(nd.__repr__())
        # print(nd for nd in self.topological_nodes(key))
        return (nd for nd in self.topological_nodes(key) if isinstance(nd, DAGOpNode))

    def topological_nodes(self, key=None):
        """
        Yield nodes in topological order.

        Args:
            key (Callable): A callable which will take a DAGNode object and
                return a string sort key. If not specified the
                :attr:`~qiskit.dagcircuit.DAGNode.sort_key` attribute will be
                used as the sort key for each node.

        Returns:
            generator(DAGOpNode, DAGInNode, or DAGOutNode): node in topological order
        """

        def _key(x):
            return x.sort_key

        if key is None:
            key = _key

        return iter(rx.lexicographical_topological_sort(self._multi_graph, key=key))
    
    def merge_output_nodes(self):
        for k in self.output_map_left.keys():
            left_v = self.output_map_left[k]
            right_v = self.output_map_right[k]

            # print(left_v)
            # print(type(left_v))

            self._multi_graph.merge_nodes(left_v._node_id, right_v._node_id)
        
    def add_qubits(self, qubits):
        # print(qubits)
        """Add individual qubit wires."""
        if any(not isinstance(qubit, Qubit) for qubit in qubits):
            raise TypeError("not a Qubit instance.")

        duplicate_qubits = set(self.qubits).intersection(qubits)
        if duplicate_qubits:
            raise ValueError("duplicate qubits %s" % duplicate_qubits)

        for qubit in qubits:
            self.qubits.append(qubit)
            self._qubit_indices[qubit] = BitLocations(len(self.qubits) - 1, [])
            self._add_wire(qubit)

    def add_qreg(self, qreg):
        """Add all wires in a quantum register."""
        if not isinstance(qreg, QuantumRegister):
            raise TypeError("not a QuantumRegister instance.")
        if qreg.name in self.qregs:
            raise KeyError("duplicate register %s" % qreg.name)
        self.qregs[qreg.name] = qreg
        existing_qubits = set(self.qubits)
        for j in range(qreg.size):
            if qreg[j] in self._qubit_indices:
                self._qubit_indices[qreg[j]].registers.append((qreg, j))
            if qreg[j] not in existing_qubits:
                self.qubits.append(qreg[j])
                self._qubit_indices[qreg[j]] = BitLocations(
                    len(self.qubits) - 1, registers=[(qreg, j)]
                )
                self._add_wire(qreg[j])

    def _add_wire(self, wire):
        """Add a qubit or bit to the circuit.

        Args:
            wire (Bit): the wire to be added

            This adds a pair of in and out nodes connected by an edge.

        Raises:
            DAGCircuitError: if trying to add duplicate wire
        """
        if wire not in self._wires:
            self._wires.add(wire)

            inp_node = DAGInNode(wire=wire)
            outp_node_left = DAGOutNode(wire=wire)
            outp_node_right = DAGOutNode(wire=wire)
            input_map_id, output_map_left_id, output_map_right_id = self._multi_graph.add_nodes_from([inp_node, outp_node_left, outp_node_right])
            inp_node._node_id = input_map_id
            outp_node_left._node_id = output_map_left_id
            outp_node_right._node_id = output_map_right_id
            self.input_map[wire] = inp_node
            self.output_map_left[wire] = outp_node_left
            self.output_map_right[wire] = outp_node_right
            self._multi_graph.add_edge(inp_node._node_id, outp_node_left._node_id, wire)
            self._multi_graph.add_edge(inp_node._node_id, outp_node_right._node_id, wire)

            outp_node_left.parents = [inp_node]
            outp_node_right.parents = [inp_node]
        else:
            # raise KeyError(f"duplicate wire {wire}")
            print(f"KeyError(duplicate wire {wire})")

    def find_bit(self, bit: Bit) -> BitLocations:
        """
        Finds locations in the circuit, by mapping the Qubit and Clbit to positional index
        BitLocations is defined as: BitLocations = namedtuple("BitLocations", ("index", "registers"))

        Args:
            bit (Bit): The bit to locate.

        Returns:
            namedtuple(int, List[Tuple(Register, int)]): A 2-tuple. The first element (``index``)
                contains the index at which the ``Bit`` can be found (in either
                :obj:`~DAGCircuit.qubits`, :obj:`~DAGCircuit.clbits`, depending on its
                type). The second element (``registers``) is a list of ``(register, index)``
                pairs with an entry for each :obj:`~Register` in the circuit which contains the
                :obj:`~Bit` (and the index in the :obj:`~Register` at which it can be found).

          Raises:
            DAGCircuitError: If the supplied :obj:`~Bit` was of an unknown type.
            DAGCircuitError: If the supplied :obj:`~Bit` could not be found on the circuit.
        """
        try:
            if isinstance(bit, Qubit):
                return self._qubit_indices[bit]
            elif isinstance(bit, Clbit):
                return self._clbit_indices[bit]
            else:
                raise TypeError(f"Could not locate bit of unknown type: {type(bit)}")
        except KeyError as err:
            raise KeyError(
                f"Could not locate provided bit: {bit}. Has it been added to the DAGCircuit?"
            ) from err
        
    def apply_operation_back(self, op, qargs=(), cargs=(), left=True, *, check=True):
        """Apply an operation to the output of the circuit.

        Args:
            op (qiskit.circuit.Operation): the operation associated with the DAG node
            qargs (tuple[~qiskit.circuit.Qubit]): qubits that op will be applied to
            cargs (tuple[Clbit]): cbits that op will be applied to
            check (bool): If ``True`` (default), this function will enforce that the
                :class:`.DAGCircuit` data-structure invariants are maintained (all ``qargs`` are
                :class:`~.circuit.Qubit`\\ s, all are in the DAG, etc).  If ``False``, the caller *must*
                uphold these invariants itself, but the cost of several checks will be skipped.
                This is most useful when building a new DAG from a source of known-good nodes.
        Returns:
            DAGOpNode: the node for the op that was added to the dag

        Raises:
            DAGCircuitError: if a leaf node is connected to multiple outputs

        """
        qargs = tuple(qargs)
        cargs = tuple(cargs)

        # if self._operation_may_have_bits(op):
        #     # This is the slow path; most of the time, this won't happen.
        #     all_cbits = set(self._bits_in_operation(op)).union(cargs)
        # else:
        #     all_cbits = cargs
        all_cbits = cargs

        if check:
            # self._check_condition(op.name, getattr(op, "condition", None))
            if left:
                self._check_bits(qargs, self.output_map_left)
            else:
                self._check_bits(qargs, self.output_map_right)
            # self._check_bits(all_cbits, self.output_map)

        node = DAGOpNode(op=op, qargs=qargs, cargs=cargs, dag=self)
        node._node_id = self._multi_graph.add_node(node)
        self._increment_op(op)

        # Add new in-edges from predecessors of the output nodes to the
        # operation node while deleting the old in-edges of the output nodes
        # and adding new edges from the operation node to each output node
        
        ref_nodes_idx = [self.output_map_left[bit]._node_id for bits in (qargs, all_cbits) for bit in bits] if left else [self.output_map_right[bit]._node_id for bits in (qargs, all_cbits) for bit in bits]
        ref_nodes = [self._multi_graph.nodes()[idx] for idx in ref_nodes_idx] # these are DAGOpNodes

        new_node_parents = set()

        # alter parents
        for child in ref_nodes:
            print(child.__repr__())
            new_node_parents.add(child.parents[0]) # each ref_node should only have one parent
            # the output node's new parent is the new node. This is because each output node identifies with one qubit/wire.
            child.parents = [node]
    
        node.parents = list(new_node_parents)

        self._multi_graph.insert_node_on_in_edges_multiple(
            node._node_id,
            ref_nodes_idx,
        )
        return node
    
    def _check_bits(self, args, amap):
        """Check the values of a list of (qu)bit arguments.

        For each element of args, check that amap contains it.

        Args:
            args (list[Bit]): the elements to be checked
            amap (dict): a dictionary keyed on Qubits/Clbits

        Raises:
            DAGCircuitError: if a qubit is not contained in amap
        """
        # Check for each wire
        for wire in args:
            if wire not in amap:
                raise ValueError(f"(qu)bit {wire} not found in {amap}")
    
    def _increment_op(self, op):
        if op.name in self._op_names:
            self._op_names[op.name] += 1
        else:
            self._op_names[op.name] = 1
    
    def draw(self, scale=0.7, filename=None, style="color"):
        """
        Draws the dag circuit.

        This function needs `Graphviz <https://www.graphviz.org/>`_ to be
        installed. Graphviz is not a python package and can't be pip installed
        (the ``graphviz`` package on PyPI is a Python interface library for
        Graphviz and does not actually install Graphviz). You can refer to
        `the Graphviz documentation <https://www.graphviz.org/download/>`__ on
        how to install it.

        Args:
            scale (float): scaling factor
            filename (str): file path to save image to (format inferred from name)
            style (str):
                'plain': B&W graph;
                'color' (default): color input/output/op nodes

        Returns:
            Ipython.display.Image: if in Jupyter notebook and not saving to file,
            otherwise None.
        """
        from qiskit.visualization.dag_visualization import dag_drawer

        return dag_drawer(dag=self, scale=scale, filename=filename, style=style)

    def front_layer(self):
        """Return a list of op nodes in the first layer of this dag."""
        graph_layers = self.multigraph_layers()
        try:
            next(graph_layers)  # Remove input nodes
        except StopIteration:
            return []

        op_nodes = [node for node in next(graph_layers) if isinstance(node, DAGOpNode)]

        return op_nodes

    def multigraph_layers(self):
        """Yield layers of the multigraph."""
        first_layer = [x._node_id for x in self.input_map.values()]
        return iter(rx.layers(self._multi_graph, first_layer))
    
    def successors(self, node):
        """Returns iterator of the successors of a node as DAGOpNodes and DAGOutNodes."""
        return iter(self._multi_graph.successors(node._node_id))