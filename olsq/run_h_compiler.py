from qiskit.transpiler import CouplingMap, Layout
from qiskit import QuantumCircuit
from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import SabreLayout, SabreSwap, ApplyLayout, SetLayout
from qiskit.converters import *
from qiskit.transpiler.passes import Unroller
from rustworkx.visualization import graphviz_draw
from qiskit.compiler import transpile
from collections import deque
from qiskit.dagcircuit import DAGDependency, DAGDepNode, DAGCircuit
from qiskit.circuit import Qubit, QuantumRegister, Gate, CircuitInstruction, Instruction
from qiskit.converters import circuit_to_dagdependency, circuit_to_dag, dag_to_circuit
import rustworkx as rx
import collections

def partition_circuit(circuit_info, index):
    if index < 0 or index >= len(circuit_info):
        print("Bad index passed into partition_circuit")
    left = reversed(circuit_info[:index])
    right = circuit_info[index:]
    return left, right

# Not working code. Only for proof of concept
def sabre_layout_pass_manager(initial_layout):
    layout_and_route = [
        SetLayout(initial_layout),
        FullAncillaAllocation(self.coupling_map),
        EnlargeWithAncilla(),
        ApplyLayout(),
        self.routing_pass,
    ]
    pm = PassManager(layout_and_route)
    return pm
    
# Not working code. Only for proof of concept
def left_pass_and_right_pass(circuit_info, index, count_physical_qubit):
    left_circuit_info_reversed, right_info_circuit = self.partition_circuit(circuit_info, index)
    left_qc = construct_qc(left_circuit_info_reversed, count_physical_qubit)
    right_qc = construct_qc(right_circuit_info, count_physical_qubit)
    
    # random initial layout
    seed = np.random.randint(0, np.iinfo(np.int32).max)
    rng = np.random.default_rng(seed)
    physical_qubits = rng.choice(self.coupling_map.size(), len(dag.qubits), replace=False)
    physical_qubits = rng.permutation(physical_qubits)
    initial_layout = Layout({q: dag.qubits[i] for i, q in enumerate(physical_qubits)})
    
    # left pass    
    pm = sabre_layout_pass_manager();
    new_circ = pm.run(left_qc)
    # Update initial layout and reverse the unmapped circuit.
    pass_final_layout = pm.property_set["final_layout"]
    final_layout = self._compose_layouts(
        initial_layout, pass_final_layout, new_circ.qregs
    )
    initial_layout = final_layout
    
    # right pass
    pm = self.sabre_layout_pass_manager();
    new_circ = pm.run(right_qc)
    # Update initial layout and reverse the unmapped circuit.
    pass_final_layout = pm.property_set["final_layout"]
    final_layout = self._compose_layouts(
        initial_layout, pass_final_layout, new_circ.qregs
    )
    return final_layout
    
    
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

def construct_qc_with_barriers(list_gate, count_physical_qubit): # list_gate is a tuple of lists
    qc = QuantumCircuit(count_physical_qubit)
    for gate in list_gate:
        if len(gate) == 2:
            qc.cx(gate[0], gate[1])
        elif len(gate) == 1:
            qc.h(gate[0])
        else:
            raise TypeError("Currently only support one and two-qubit gate.")
        qc.barrier()
    return qc

def run_sabre_on_dag(dagcircuit, coupling, orig, layout_trials):
    device = CouplingMap(couplinglist = coupling, description="sabre_test")
    # sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1)
    sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=layout_trials)
    
    out_dag = sbl.run(dagcircuit)
    sabre_cir = dag_to_circuit(out_dag)
    
    # if orig:
    #     sabre_cir.draw(scale=0.7, filename="sabrecir_orig.png", output='mpl', style='color')
    # else:
    #     sabre_cir.draw(scale=0.7, filename="sabrecir_from_dag.png", output='mpl', style='color')
    
    count_swap = 0
    for gate in sabre_cir.data:
        # print(gate[0].name)
        # print(gate[0].num_qubits)
        if gate[0].name == 'swap':
            count_swap += 1

    return count_swap, sabre_cir.depth()
    
    

def run_sabre(circuit_info, coupling, count_physical_qubit, layout_trials):
    # read qasm
    print("circuit_info")
    print(type(circuit_info))
    print(circuit_info)
    list_gate = circuit_info
    qc = construct_qc(list_gate, count_physical_qubit)
    # qc.draw(scale=0.7, filename = "orig_circuit.png", output='mpl', style='color')
    
    # qc_with_barriers = construct_qc_with_barriers(list_gate, count_physical_qubit)
    # qc_with_barriers.draw(scale=0.7, filename = "orig_circuit_with_barriers.png", output='mpl', style='color', plot_barriers = False)
    
    device = CouplingMap(couplinglist = coupling, description="sabre_test")
    img = device.draw()
    img.save("coupling_map.png")
    
    # print("qubits")
    # print(qc.qubits)
    # print("qregs")
    # print(qc.qregs)
    # print("instructions")
    # print(qc.data)
    
    orig_dagcircuit = circuit_to_dag(qc)
    orig_dagcircuit.draw(scale=0.7, filename='orig_dagcircuit.png', style='color')
    
    count_swap, depth = run_sabre_on_dag(orig_dagcircuit, coupling, True, layout_trials)
    
    return count_swap, depth
    
    # # initialize sabre
    # # ["basic", "lookahead", "decay"]
    # # sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1)
    # sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=1)
    # pass_manager1 = PassManager(sbl)
    # sabre_cir = pass_manager1.run(qc)
    # # pass_manager2 = PassManager(sbs)
    # # sabre_cir = pass_manager2.run(sabre_cir)
#     sabre_cir.draw(scale=0.7, filename="sabrecir.png", output='mpl', style='color')
    
#     count_swap = 0
#     for gate in sabre_cir.data:
#         # print(gate[0].name)
#         # print(gate[0].num_qubits)
#         if gate[0].name == 'swap':
#             count_swap += 1

#     return count_swap, sabre_cir.depth()

def _add_gate_to_dagcircuit(gate, qubit_array, dagcircuit):
    if len(gate) == 1:
        instruction = CircuitInstruction(operation=Instruction(name='h', num_qubits=1, num_clbits=0, params=[]), qubits=[qubit_array[gate[0]]])
        dagcircuit.apply_operation_back(instruction.operation, instruction.qubits, instruction.clbits)
        
    elif len(gate) == 2:
        instruction = CircuitInstruction(operation=Instruction(name='cx', num_qubits=2, num_clbits=0, params=[]), qubits=(qubit_array[gate[0]], qubit_array[gate[1]]))
        dagcircuit.apply_operation_back(instruction.operation, instruction.qubits, instruction.clbits)


def construct_dagcircuit3(circuit_info, coupling, count_physical_qubit, index, circuit_name): 
    dagcircuit = DAGCircuit()
#     qregs = [QuantumRegister(size=16, name='q') for i in range(count_physical_qubit)]
    
    qubit_array = [Qubit(register=QuantumRegister(size=count_physical_qubit, name='q'), index=i) for i in range(count_physical_qubit)]

    if type(qubit_array)== Qubit:
        print(f"qubit_array of type {type(qubit_array)} is {qubit_array}")
    
    dagcircuit.add_qubits(qubit_array)
    
    left_queue = collections.deque(reversed(circuit_info[:index]))
    # print("left queue")
    # print(left_queue)
    right_queue = collections.deque(circuit_info[index+1:])
    # print("right queue")
    # print(right_queue)
    
    _add_gate_to_dagcircuit(circuit_info[index], qubit_array, dagcircuit)
    
    while left_queue and right_queue:
        l = left_queue.popleft()
        r = right_queue.popleft()
        _add_gate_to_dagcircuit(l, qubit_array, dagcircuit)
        _add_gate_to_dagcircuit(r, qubit_array, dagcircuit)
        
    while left_queue:
        l = left_queue.popleft()
        _add_gate_to_dagcircuit(l, qubit_array, dagcircuit)
    
    while right_queue:
        r = right_queue.popleft()
        _add_gate_to_dagcircuit(r, qubit_array, dagcircuit)
        
    # img = dagcircuit.draw(scale=0.7, style='color') # filename='images/{}/index_{}_dagcircuit.png'.format(circuit_name, index),
    # img.save('images/{}/index_{}_dagcircuit.png'.format(circuit_name, index))
    
    return dagcircuit
        
        

# def construct_dagcircuit2(circuit_info, coupling, count_physical_qubit, index):
#     graph = rx.PyDAG()
#     root_gate = circuit_info[index]
#     root_idx = graph.add_node(root_gate)
    
#     # seen_right
    
#     seen_right = {root_gate[0]: root_idx}
#     if len(root_gate) == 2:
#         seen_right[root_gate[1]] = root_idx
    
#     for gate in circuit_info[index+1:]:
#         new_node_idx = graph.add_node(gate)
#         if gate[0] in seen_right:
#             graph.add_edge(seen_right[gate[0]], new_node_idx, (seen_right[gate[0]], new_node_idx))
#             seen_right[gate[0]] = new_node_idx
#         if len(gate) == 2 and gate[1] in seen_right:
#             graph.add_edge(seen_right[gate[1]], new_node_idx, (seen_right[gate[1]], new_node_idx))
#             seen_right[gate[1]] = new_node_idx
            
#     # seen_left
            
#     seen_left = {root_gate[0]: root_idx}
#     if  len(root_gate) == 2:
#         seen_left[root_gate[0]] = root_idx
    
#     for gate in reversed(circuit_info[:index]):
#         new_node_idx = graph.add_node(gate)
#         if gate[0] in seen_left:
#             graph.add_edge(seen_left[gate[0]], new_node_idx, (seen_left[gate[0]], new_node_idx))
#             seen_left[gate[0]] = new_node_idx
#         if len(gate) == 2 and gate[1] in seen_left:
#             graph.add_edge(seen_left[gate[1]], new_node_idx, (seen_left[gate[1]], new_node_idx))
#             seen_left[gate[1]] = new_node_idx
        
#     graph.draw(scale=0.7, filename='pydag.png', style='color')
#     return graph
        
def construct_dagcircuit(circuit_info, coupling, count_physical_qubit, index):
    if index < 0 or index >= len(circuit_info):
        print("Bad index passed into partition_circuit")
    left_circuit_info_reversed = reversed(circuit_info[:index])
    right_circuit_info = circuit_info[index+1:]
    
    print("left_circuit_info_reversed")
    print(left_circuit_info_reversed)
    print("right_circuit_info")
    print(right_circuit_info)
    left_qc = construct_qc(left_circuit_info_reversed, count_physical_qubit)
    right_qc = construct_qc(right_circuit_info, count_physical_qubit)
    
    left_dag = circuit_to_dag(left_qc)
    right_dag = circuit_to_dag(right_qc)
    
    left_dag.draw(scale=0.7, filename='left_dagcircuit.png', style='color')
    right_dag.draw(scale=0.7, filename='right_dagcircuit.png', style='color')
    
    print("left dagcircuit")
    print(left_dag)
    print("front layer")
    print(left_dag.front_layer())
    
    print("right dagcircuit")
    print(right_dag)
    print("front layer")
    print(right_dag.front_layer())
    
    combined_front_layer = set(left_dag.front_layer())
    for r in right_dag.front_layer():
        combined_front_layer.add(r)
    
    graph = rx.PyDAG()
    graph.add_nodes_from(list(combined_front_layer))
    
    print("New graph nodes")
    print(graph.nodes())

def construct_dagdependency(circuit_info, coupling, count_physical_qubit, index):
    print("circuit_info")
    print(circuit_info)
    """
        Example Circuit:
        ([4, 15], [4, 11], [4, 10], [15, 10], [15, 7], [0, 5], [0, 13], [0, 12], [5, 9], [5, 1], [2, 11], [2, 7], [2, 12], [11, 1], [1, 9], [9, 7], [10, 8], [13, 14], [13, 6], [14, 6], [14, 8], [6, 3], [3, 12], [3, 8])
    """
    if index < 0 or index >= len(circuit_info):
        print("Bad index passed into partition_circuit")
    left_circuit_info_reversed = reversed(circuit_info[:index + 1])
    right_circuit_info = circuit_info[index:]
    print("left_circuit_info_reversed")
    print(left_circuit_info_reversed)
    print("right_circuit_info")
    print(right_circuit_info)
    left_qc = construct_qc(left_circuit_info_reversed, count_physical_qubit)
    right_qc = construct_qc(right_circuit_info, count_physical_qubit)
    
    # create left dagdependency
    left_dag = circuit_to_dagdependency(left_qc)
    # create right dagdependency
    right_dag = circuit_to_dagdependency(right_qc)
    # MISSING: connect two DAGs by joining left head's children with the right head's children
    
    left_dag.draw(scale=0.7, filename='left_dagdependency.png', style='color')
    right_dag.draw(scale=0.7, filename='right_dagdependency.png', style='color')
    
    
def left_layout_and_right_routing(circuit_info, coupling, count_physical_qubit, index):
    qc = construct_qc(circuit_info, count_physical_qubit)
    qc.draw(scale=0.7, filename = "orig_circuit.png", output='mpl', style='color')
    
    left_circuit_reversed = reversed(circuit_info[:index+1])
    if index + 1 == len(circuit_info):
        right_circuit = () # empty tuple
    else:
        right_circuit = circuit_info[index+1:]
        
    qc_left = construct_qc(left_circuit_reversed, count_physical_qubit)
    qc_right = construct_qc(right_circuit, count_physical_qubit)
    device = CouplingMap(couplinglist = coupling, description="sabre_test")
    
    # sabre_cir = transpile(qc, coupling_map=device, layout_method='sabre', routing_method='sabre', seed_transpiler=0)
    
    # run SabreLayout on left circuit
    sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=1)
    pass_manager1 = PassManager(sbl)
    sabre_cir_left = pass_manager1.run(qc_left)
    sabre_cir_left.draw(scale=0.7, filename="sabrecir_left.png", output='mpl', style='color')
    
    # Apply layout on right circuit
    slt = SetLayout(sbl.property_set['layout'])
    apl = ApplyLayout()
    pass_manager2 = PassManager(slt, apl)
    sabre_cir_right = pass_manager2.run(qc_right)
    sabre_cir_right.draw(scale=0.7, filename="sabrecir_right.png", output='mpl', style='color')
    
    # join the left and right circuit
    sabre_cir_left = sabre_cir_left.reverse_ops()
    joined_cir = sabre_cir_left.compose(sabre_cir_right)
    # run SabreSwap on the joined circuit
    sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1)
    pass_manager3 = PassManager(sbs)
    joined_cir = pass_manager3.run(joined_cir)
    joined_cir.draw(scale=0.7, filename="sabre_left_then_right_cir.png", output='mpl', style='color')
    
    
    count_swap = 0
    
    for gate in joined_cir.data:
        # print(gate[0].name)
        # print(gate[0].num_qubits)
        if gate[0].name == 'swap':
            count_swap += 1

    return count_swap, joined_cir.depth()
    

def right_layout_and_left_routing(circuit_info, coupling, count_physical_qubit, index):
    left_circuit_reversed = reversed(circuit_info[:index+1])
    if index + 1 == len(circuit_info):
        right_circuit = () # empty tuple
    else:
        right_circuit = circuit_info[index+1:]
        
    qc_left = construct_qc(left_circuit_reversed, count_physical_qubit)
    qc_right = construct_qc(right_circuit, count_physical_qubit)
    device = CouplingMap(couplinglist = coupling, description="sabre_test")
    
    # sabre_cir = transpile(qc, coupling_map=device, layout_method='sabre', routing_method='sabre', seed_transpiler=0)
    
    # run SabreLayout on right circuit
    sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=1)
    pass_manager1 = PassManager(sbl)
    sabre_cir_right = pass_manager1.run(qc_right)
    sabre_cir_right.draw(scale=0.7, filename="sabrecir_right.png", output='mpl', style='color')
    
    # Apply layout on left circuit
    slt = SetLayout(sbl.property_set['layout'])
    apl = ApplyLayout()
    pass_manager2 = PassManager(slt, apl)
    sabre_cir_left = pass_manager2.run(qc_left)
    sabre_cir_left.draw(scale=0.7, filename="sabrecir_left.png", output='mpl', style='color', with_layout=True)
    
    # join the left and right circuit
    sabre_cir_left = sabre_cir_left.reverse_ops()
    joined_cir = sabre_cir_left.compose(sabre_cir_right)
    # run SabreSwap on the joined circuit
    sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1)
    pass_manager3 = PassManager(sbs)
    joined_cir = pass_manager3.run(joined_cir)
    joined_cir.draw(scale=0.7, filename="sabre_right_then_left_cir.png", output='mpl', style='color', with_layout=True)
    count_swap = 0
    
    for gate in joined_cir.data:
        # print(gate[0].name)
        # print(gate[0].num_qubits)
        if gate[0].name == 'swap':
            count_swap += 1

    return count_swap, joined_cir.depth()