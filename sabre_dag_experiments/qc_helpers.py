from qiskit.transpiler import CouplingMap
from qiskit import QuantumCircuit
from qiskit.transpiler import PassManager
from sabre_dag_experiments.sabre_swap import SabreSwap
from qiskit.transpiler.passes import SabreLayout, ApplyLayout, SetLayout
from qiskit.converters import *

from sabre_dag_experiments.bidag_sabre_swap import BiDAGSabreSwap

def partition_circuit(circuit_info, index):
    if index < 0 or index >= len(circuit_info):
        print("Bad index passed into partition_circuit")
    left = reversed(circuit_info[:index])
    right = circuit_info[index:]
    return left, right
    
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

# The purpose of this method is to draw the circuit without layers pushed left
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

def apply_layout_and_generate_sabre_swaps(circuit_info, coupling, count_physical_qubit, initial_mapping, left, index, layout_trials):
    if left:
      qc = construct_qc(reversed(circuit_info[:index]), count_physical_qubit)
    else:
      qc = construct_qc(circuit_info[index:], count_physical_qubit)
    device = CouplingMap(couplinglist = coupling, description="sabre_test")

    # sbs = BiDAGSabreSwap(bidag=bidag, coupling_map=device, initial_mapping=initial_mapping, heuristic="basic", seed=None, trials=None)
    # swaps, final_mapping = sbs.run()
    # print("final sabre result")
    # print(swaps)
    # print(f"{len(swaps)} swaps")

    sl = SetLayout(initial_mapping)
    apl = ApplyLayout()
    sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1, initial_mapping=initial_mapping)
    pm1 = PassManager([sl, apl, sbs])
    sabre_cir = pm1.run(qc)
    
    # if left:
    #   print(f"Drawing left circuit at bidag_index_{index}_left_circuit.png")
    #   sabre_cir.draw(scale=0.7, filename=f"bidag_index_{index}_left_circuit.png", output='mpl', style='color', with_layout=True)
    # else:
    #   print(f"Drawing right circuit at bidag_index_{index}_right_circuit.png")
    #   sabre_cir.draw(scale=0.7, filename=f"bidag_index_{index}_right_circuit.png", output='mpl', style='color', with_layout=True)
    
    count_swap = 0
    for gate in sabre_cir.data:
        if gate[0].name == 'swap':
            count_swap += 1

    return count_swap, sabre_cir.depth()
    
def run_sabre(circuit_info, coupling, count_physical_qubit, layout_trials):
    # read qasm
    list_gate = circuit_info
    qc = construct_qc(list_gate, count_physical_qubit)
    device = CouplingMap(couplinglist = coupling, description="sabre_test")
    
    sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=layout_trials)
    pass_manager1 = PassManager(sbl)
    sabre_cir = pass_manager1.run(qc)
    # sabre_cir.draw(scale=0.7, filename="sabrecir.png", output='mpl', style='color')
    
    count_swap = 0
    for gate in sabre_cir.data:
        if gate[0].name == 'swap':
            count_swap += 1

    return count_swap, sabre_cir.depth()
        
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
    
    
# def left_layout_and_right_routing(circuit_info, coupling, count_physical_qubit, index):
#     qc = construct_qc(circuit_info, count_physical_qubit)
#     qc.draw(scale=0.7, filename = "orig_circuit.png", output='mpl', style='color')
    
#     left_circuit_reversed = reversed(circuit_info[:index+1])
#     if index + 1 == len(circuit_info):
#         right_circuit = () # empty tuple
#     else:
#         right_circuit = circuit_info[index+1:]
        
#     qc_left = construct_qc(left_circuit_reversed, count_physical_qubit)
#     qc_right = construct_qc(right_circuit, count_physical_qubit)
#     device = CouplingMap(couplinglist = coupling, description="sabre_test")
    
#     # sabre_cir = transpile(qc, coupling_map=device, layout_method='sabre', routing_method='sabre', seed_transpiler=0)
    
#     # run SabreLayout on left circuit
#     sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=1)
#     pass_manager1 = PassManager(sbl)
#     sabre_cir_left = pass_manager1.run(qc_left)
#     sabre_cir_left.draw(scale=0.7, filename="sabrecir_left.png", output='mpl', style='color')
    
#     # Apply layout on right circuit
#     slt = SetLayout(sbl.property_set['layout'])
#     apl = ApplyLayout()
#     pass_manager2 = PassManager(slt, apl)
#     sabre_cir_right = pass_manager2.run(qc_right)
#     sabre_cir_right.draw(scale=0.7, filename="sabrecir_right.png", output='mpl', style='color')
    
#     # join the left and right circuit
#     sabre_cir_left = sabre_cir_left.reverse_ops()
#     joined_cir = sabre_cir_left.compose(sabre_cir_right)
#     # run SabreSwap on the joined circuit
#     sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1)
#     pass_manager3 = PassManager(sbs)
#     joined_cir = pass_manager3.run(joined_cir)
#     joined_cir.draw(scale=0.7, filename="sabre_left_then_right_cir.png", output='mpl', style='color')
    
    
#     count_swap = 0
    
#     for gate in joined_cir.data:
#         # print(gate[0].name)
#         # print(gate[0].num_qubits)
#         if gate[0].name == 'swap':
#             count_swap += 1

#     return count_swap, joined_cir.depth()
    

# def right_layout_and_left_routing(circuit_info, coupling, count_physical_qubit, index):
#     left_circuit_reversed = reversed(circuit_info[:index+1])
#     if index + 1 == len(circuit_info):
#         right_circuit = () # empty tuple
#     else:
#         right_circuit = circuit_info[index+1:]
        
#     qc_left = construct_qc(left_circuit_reversed, count_physical_qubit)
#     qc_right = construct_qc(right_circuit, count_physical_qubit)
#     device = CouplingMap(couplinglist = coupling, description="sabre_test")
    
#     # sabre_cir = transpile(qc, coupling_map=device, layout_method='sabre', routing_method='sabre', seed_transpiler=0)
    
#     # run SabreLayout on right circuit
#     sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=1)
#     pass_manager1 = PassManager(sbl)
#     sabre_cir_right = pass_manager1.run(qc_right)
#     sabre_cir_right.draw(scale=0.7, filename="sabrecir_right.png", output='mpl', style='color')
    
#     # Apply layout on left circuit
#     slt = SetLayout(sbl.property_set['layout'])
#     apl = ApplyLayout()
#     pass_manager2 = PassManager(slt, apl)
#     sabre_cir_left = pass_manager2.run(qc_left)
#     sabre_cir_left.draw(scale=0.7, filename="sabrecir_left.png", output='mpl', style='color', with_layout=True)
    
#     # join the left and right circuit
#     sabre_cir_left = sabre_cir_left.reverse_ops()
#     joined_cir = sabre_cir_left.compose(sabre_cir_right)
#     # run SabreSwap on the joined circuit
#     sbs = SabreSwap(coupling_map = device, heuristic = "lookahead", seed = 0, trials=1)
#     pass_manager3 = PassManager(sbs)
#     joined_cir = pass_manager3.run(joined_cir)
#     joined_cir.draw(scale=0.7, filename="sabre_right_then_left_cir.png", output='mpl', style='color', with_layout=True)
#     count_swap = 0
    
#     for gate in joined_cir.data:
#         # print(gate[0].name)
#         # print(gate[0].num_qubits)
#         if gate[0].name == 'swap':
#             count_swap += 1

#     return count_swap, joined_cir.depth()