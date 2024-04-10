from qiskit.transpiler import CouplingMap
from qiskit import QuantumCircuit
from qiskit.transpiler.passes import SabreLayout
from qiskit.converters import *
from qiskit.dagcircuit import DAGCircuit
from sabre_dag_experiments.bidirectional_dag_circuit import BidirectionalDAGCircuit
from qiskit.circuit import Qubit, QuantumRegister, CircuitInstruction, Instruction
import copy

# Several methods to construct, manipulate, and transpile a DAGCircuit

def circuit_to_dag(circuit, copy_operations=True, *, qubit_order=None, clbit_order=None):
    """
        Copied from Qiskit, but the intention is to build a DAGCircuit using my own class instead of theirs
    """
    dagcircuit = DAGCircuit()
    dagcircuit.name = circuit.name
    dagcircuit.global_phase = circuit.global_phase
    dagcircuit.calibrations = circuit.calibrations
    dagcircuit.metadata = circuit.metadata

    if qubit_order is None:
        qubits = circuit.qubits
    elif len(qubit_order) != circuit.num_qubits or set(qubit_order) != set(circuit.qubits):
        raise ValueError("'qubit_order' does not contain exactly the same qubits as the circuit")
    else:
        qubits = qubit_order

    # if clbit_order is None:
    #     clbits = circuit.clbits
    # elif len(clbit_order) != circuit.num_clbits or set(clbit_order) != set(circuit.clbits):
    #     raise ValueError("'clbit_order' does not contain exactly the same clbits as the circuit")
    # else:
    #     clbits = clbit_order

    dagcircuit.add_qubits(qubits)
    # dagcircuit.add_clbits(clbits)

    for register in circuit.qregs:
        dagcircuit.add_qreg(register)

    # for register in circuit.cregs:
    #     dagcircuit.add_creg(register)

    for instruction in circuit.data:
        op = instruction.operation
        if copy_operations:
            op = copy.deepcopy(op)
        dagcircuit.apply_operation_back(op, instruction.qubits, instruction.clbits, check=False)

    dagcircuit.duration = circuit.duration
    dagcircuit.unit = circuit.unit
    return dagcircuit

# Adds a gate to LEFT or Right dagcircuit. Additional parameter 'left'
def _add_gate_to_dagcircuit(gate, qubit_array, bidirectional_dagcircuit, left):
    if len(gate) == 1:
        instruction = CircuitInstruction(operation=Instruction(name='h', num_qubits=1, num_clbits=0, params=[]), qubits=[qubit_array[gate[0]]])
        bidirectional_dagcircuit.apply_operation_back(instruction.operation, instruction.qubits, instruction.clbits, left)
        
    elif len(gate) == 2:
        instruction = CircuitInstruction(operation=Instruction(name='cx', num_qubits=2, num_clbits=0, params=[]), qubits=(qubit_array[gate[0]], qubit_array[gate[1]]))
        bidirectional_dagcircuit.apply_operation_back(instruction.operation, instruction.qubits, instruction.clbits, left)

def construct_qc(list_gate, count_physical_qubit): # list_gate is a tuple of lists
    qc = QuantumCircuit(count_physical_qubit)
    for gate in list_gate:
        if len(gate) == 2:
            qc.cx(gate[0], gate[1])
        elif len(gate) == 1:
            qc.h(gate[0])
        else:
            raise TypeError("Currently only support one and two-qubit gate.")
    return qc

def construct_reverse_bidirectional_dagcircuit(dag, count_physical_qubit, index):
    graph = BidirectionalDAGCircuit()
    qubit_array = [Qubit(register=QuantumRegister(size=count_physical_qubit, name='q'), index=i) for i in range(count_physical_qubit)]
    graph.add_qubits(qubit_array)

    print("reverse applied nodes left")
    print(reversed(dag.applied_nodes_left))

    print("reverse applied nodes right")
    print(reversed(dag.applied_nodes_right))

    for gate in reversed(dag.applied_nodes_left):
        gate_tuple = tuple([qubit.index for qubit in gate.qargs])
        _add_gate_to_dagcircuit(gate_tuple, qubit_array, graph, True)

    for gate in reversed(dag.applied_nodes_right):
        gate_tuple = tuple([qubit.index for qubit in gate.qargs])
        _add_gate_to_dagcircuit(gate_tuple, qubit_array, graph, False)
    
    # For Visualization
    # bidag = graph.draw(scale=0.7, style='color')
    # bidag.save(f'reverse_bidirectional_dagcircuit_index_{index}.png')
    
    return graph
    

def construct_bidirectional_dagcircuit(circuit_info, count_physical_qubit, index):
    left_circuit_info = reversed(circuit_info[:index])
    right_circuit_info = circuit_info[index:]

    graph = BidirectionalDAGCircuit()
    qubit_array = [Qubit(register=QuantumRegister(size=count_physical_qubit, name='q'), index=i) for i in range(count_physical_qubit)]
    graph.add_qubits(qubit_array)

    for gate in left_circuit_info:
        _add_gate_to_dagcircuit(gate, qubit_array, graph, True)
    for gate in right_circuit_info:
        _add_gate_to_dagcircuit(gate, qubit_array, graph, False)
    
    return graph

def run_sabre_on_dag(dagcircuit, coupling, layout_trials):
    device = CouplingMap(couplinglist = coupling, description="sabre_test")
    # sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1)
    sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=layout_trials, skip_routing=True)
    
    out_dag = sbl.run(dagcircuit)
    initial_layout = sbl.property_set['layout']
    
    sabre_cir = dag_to_circuit(out_dag)
    
    count_swap = 0
    for gate in sabre_cir.data:
        if gate[0].name == 'swap':
            count_swap += 1

    return initial_layout, sabre_cir, count_swap, sabre_cir.depth()

# def construct_dagcircuit(circuit_info, coupling, count_physical_qubit, index):
#     if index < 0 or index >= len(circuit_info):
#         print("Bad index passed into partition_circuit")
#     left_circuit_info_reversed = reversed(circuit_info[:index])
#     right_circuit_info = circuit_info[index+1:]
    
#     print("left_circuit_info_reversed")
#     print(left_circuit_info_reversed)
#     print("right_circuit_info")
#     print(right_circuit_info)
#     left_qc = construct_qc(left_circuit_info_reversed, count_physical_qubit)
#     right_qc = construct_qc(right_circuit_info, count_physical_qubit)
    
#     left_dag = circuit_to_dag(left_qc)
#     right_dag = circuit_to_dag(right_qc)
    
#     left_dag.draw(scale=0.7, filename='left_dagcircuit.png', style='color')
#     right_dag.draw(scale=0.7, filename='right_dagcircuit.png', style='color')
    
#     print("left dagcircuit")
#     print(left_dag)
#     print("front layer")
#     print(left_dag.front_layer())
    
#     print("right dagcircuit")
#     print(right_dag)
#     print("front layer")
#     print(right_dag.front_layer())
    
#     combined_front_layer = set(left_dag.front_layer())
#     for r in right_dag.front_layer():
#         combined_front_layer.add(r)
    
#     graph = rx.PyDAG()
#     graph.add_nodes_from(list(combined_front_layer))
    
#     print("New graph nodes")
#     print(graph.nodes())

# def construct_dagdependency(circuit_info, coupling, count_physical_qubit, index):
#     print("circuit_info")
#     print(circuit_info)
#     """
#         Example Circuit:
#         ([4, 15], [4, 11], [4, 10], [15, 10], [15, 7], [0, 5], [0, 13], [0, 12], [5, 9], [5, 1], [2, 11], [2, 7], [2, 12], [11, 1], [1, 9], [9, 7], [10, 8], [13, 14], [13, 6], [14, 6], [14, 8], [6, 3], [3, 12], [3, 8])
#     """
#     if index < 0 or index >= len(circuit_info):
#         print("Bad index passed into partition_circuit")
#     left_circuit_info_reversed = reversed(circuit_info[:index + 1])
#     right_circuit_info = circuit_info[index:]
#     print("left_circuit_info_reversed")
#     print(left_circuit_info_reversed)
#     print("right_circuit_info")
#     print(right_circuit_info)
#     left_qc = construct_qc(left_circuit_info_reversed, count_physical_qubit)
#     right_qc = construct_qc(right_circuit_info, count_physical_qubit)
    
#     # create left dagdependency
#     left_dag = circuit_to_dagdependency(left_qc)
#     # create right dagdependency
#     right_dag = circuit_to_dagdependency(right_qc)
#     # MISSING: connect two DAGs by joining left head's children with the right head's children
    
#     left_dag.draw(scale=0.7, filename='left_dagdependency.png', style='color')
#     right_dag.draw(scale=0.7, filename='right_dagdependency.png', style='color')

# def construct_dagcircuit_queue_method(circuit_info, coupling, count_physical_qubit, index, circuit_name): 
#     dagcircuit = DAGCircuit()
# #     qregs = [QuantumRegister(size=16, name='q') for i in range(count_physical_qubit)]
    
#     qubit_array = [Qubit(register=QuantumRegister(size=count_physical_qubit, name='q'), index=i) for i in range(count_physical_qubit)]

#     if type(qubit_array)== Qubit:
#         print(f"qubit_array of type {type(qubit_array)} is {qubit_array}")
    
#     dagcircuit.add_qubits(qubit_array)
    
#     left_queue = collections.deque(reversed(circuit_info[:index]))
#     # print("left queue")
#     # print(left_queue)
#     right_queue = collections.deque(circuit_info[index+1:])
#     # print("right queue")
#     # print(right_queue)
    
#     _add_gate_to_dagcircuit(circuit_info[index], qubit_array, dagcircuit)
    
#     while left_queue and right_queue:
#         l = left_queue.popleft()
#         r = right_queue.popleft()
#         _add_gate_to_dagcircuit(l, qubit_array, dagcircuit)
#         _add_gate_to_dagcircuit(r, qubit_array, dagcircuit)
        
#     while left_queue:
#         l = left_queue.popleft()
#         _add_gate_to_dagcircuit(l, qubit_array, dagcircuit)
    
#     while right_queue:
#         r = right_queue.popleft()
#         _add_gate_to_dagcircuit(r, qubit_array, dagcircuit)
        
#     # img = dagcircuit.draw(scale=0.7, style='color') # filename='{}/index_{}_dagcircuit.png'.format(circuit_name, index),
#     # img.save('{}/index_{}_dagcircuit.png'.format(circuit_name, index))
    
#     return dagcircuit