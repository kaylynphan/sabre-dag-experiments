from qiskit.transpiler import CouplingMap, Layout
from qiskit import QuantumCircuit
from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import SabreLayout, SabreSwap, ApplyLayout, SetLayout
from qiskit.converters import *
from qiskit.transpiler.passes import Unroller
from rustworkx.visualization import graphviz_draw
from qiskit.compiler import transpile
from collections import deque
from qiskit.dagcircuit import DAGDependency, DAGDepNode
from qiskit.converters import circuit_to_dagdependency, circuit_to_dag
import rustworkx as rx

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
    

def run_sabre(circuit_info, coupling, count_physical_qubit):
    # read qasm
    print("circuit_info")
    print(type(circuit_info))
    print(circuit_info)
    list_gate = circuit_info
    qc = construct_qc(list_gate, count_physical_qubit)
    qc.draw(scale=0.7, filename = "orig_circuit.png", output='mpl', style='color')
    device = CouplingMap(couplinglist = coupling, description="sabre_test")
    img = device.draw()
    img.save("coupling_map.png")
    
    # initialize sabre
    # ["basic", "lookahead", "decay"]
    sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1)
    sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=1)
    pass_manager1 = PassManager(sbl)
    sabre_cir = pass_manager1.run(qc)
    pass_manager2 = PassManager(sbs)
    sabre_cir = pass_manager2.run(sabre_cir)
    sabre_cir.draw(scale=0.7, filename="sabrecir2.png", output='mpl', style='color')
    
    count_swap = 0
    for gate in sabre_cir.data:
        # print(gate[0].name)
        # print(gate[0].num_qubits)
        if gate[0].name == 'swap':
            count_swap += 1

    return count_swap, sabre_cir.depth()
        
def construct_dagcircuit(circuit_info, coupling, count_physical_qubit, index):
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