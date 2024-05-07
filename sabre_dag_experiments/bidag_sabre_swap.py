from qiskit._accelerate.nlayout import NLayout
from qiskit import QuantumRegister, QuantumCircuit
from sabre_dag_experiments.bidag_op_node import DAGOpNode
import numpy as np
import random
import copy

import rustworkx
from qiskit._accelerate.sabre_swap import (
    build_swap_map,
    Heuristic,
    NeighborTable,
    SabreDAG,
)

class BiDAGSabreSwap:

  def __init__(self, bidag, coupling_map, initial_mapping, heuristic="basic", seed=None, trials=None):
    # SET VARIABLES
    self.bidag = bidag
    self.num_qubits = bidag.num_qubits()
    self.coupling_map = coupling_map
    self.heuristic = heuristic
    random.seed(seed)
    self.trials = trials

    # COMPUTE DISTANCE MATRIX
    self.dist_matrix = self.coupling_map.distance_matrix
    print("distance matrix:")
    print(self.dist_matrix)

    # CREATE NEIGHBOR TABLE
    self.neighbor_table = self.create_neighbor_table(self.coupling_map.graph)
    print("neighbor table")
    print(self.neighbor_table)
          
    self.restarts = 0

    ############## SET INITIAL LAYOUT


    # canonical_register = QuantumRegister(self.coupling_map.size(), 'q')
    # self._qubit_indices = {idx: bit for idx, bit in enumerate(canonical_register)}

    # print(initial_mapping)

    # print(self._qubit_indices)
    # self.initial_mapping = {
    #   v: self._qubit_indices[k] for k, v in initial_mapping.items()
    # }
    # # self.reverse_mapping = {
    # #   v: self._qubit_indices[k] for k, v in initial_mapping.get_virtual_bits().items()
    # # }
    # print("initial mapping")
    # print(self.initial_mapping)

    self.initial_mapping = initial_mapping
    # initial_layout = NLayout(layout_mapping, len(bidag.qubits), self.coupling_map.size())

    # SKIP DAG GENERATION. ALREADY GIVEN WITH BIDAG

  def restart(self, swap):
    F = self.initialize_front_layer()
    new_mapping = self.execute_swap(swap, self.initial_mapping)
    self.restarts = self.restarts + 1
    return F, new_mapping
  
  def run(self):
    # RUN SABRE ALGORITHM

    # CONSTRUCT FRONT LAYER AND OUTPUT VARIABLES
    F = self.initialize_front_layer()
    self.mutable_mapping = self.initial_mapping.copy()

    print("mutable_mapping")
    print(self.mutable_mapping)
    final_mapping = None
    inserted_swaps = []
    self.executed_gates_set = set()

    final_qc = QuantumCircuit(self.num_qubits)

    def extract_gate_qargs(node_list):
      gates = []
      for node in node_list:
        if isinstance(node, DAGOpNode):
          qubits = node.qargs
          gate_idxs = tuple([q.index for q in qubits])
          gates.append(gate_idxs)

      return gates

    # for _ in range(10):
    while len(F) > 0: # while F is not empty:
      print(f"F: {extract_gate_qargs(F)}")
      execute_gate_list = []
      for gate in F:
        if self.can_execute_gate(gate):
          # print('can execute')
          execute_gate_list.append(gate)
          if len(gate.qargs) == 1:
            final_qc.h(gate.qargs[0].index)
          else:
            final_qc.cx(gate.qargs[0].index, gate.qargs[1].index)
      print(f"execute_gate_list: {extract_gate_qargs(execute_gate_list)}")
      if len(execute_gate_list) > 0:
        for gate in execute_gate_list:
          F.remove(gate)
          # if gate in self.executed_gates_set:
          #   print("looks like gate uniqueness is not IDed")
          self.executed_gates_set.add(gate)
          print(f'removing gate {extract_gate_qargs([gate])}')
          successors = self.get_successors(gate)
          print(f'successors: {extract_gate_qargs(successors)}')
          for s in successors:
            print(f"parents of successor {extract_gate_qargs([s])}: {extract_gate_qargs(s.parents)}")
            if self.has_resolved_dependencies(s):
              print(f"successor {extract_gate_qargs([s])} has resolved dependencies")
              F.append(s)
      else:
        F_targets = self.get_F_targets(F)
        swap_candidate_list = self.obtain_swaps(F_targets)
        print("swap candidates")
        print(swap_candidate_list)
        min_swap = [] # initialize
        best_score = float("inf") # initialize
        best_mapping = self.mutable_mapping
        
        for swap in swap_candidate_list:
          score, new_mapping = self.score_temp_mapping(swap, self.mutable_mapping, F)
          if score < best_score:
            best_score = score
            min_swap = [swap]
            best_mapping = [new_mapping]
          elif score == best_score:
            min_swap.append(swap)
            best_mapping.append(new_mapping)
        # print("old mapping")
        # print(self.mutable_mapping)
        chosen_idx = random.randint(0, len(min_swap) - 1)
        chosen_mapping = best_mapping[chosen_idx]
        chosen_swap = min_swap[chosen_idx]
        print(f"chosen swap: {chosen_swap}")
        print("new mapping")
        print(chosen_mapping)

        # Remove this and replace with post-processing
        # if len(self.executed_gates_set) == 0 and self.restarts <= 10:
        #   print("swap required before any gates have been able to execute. Restart the process")
        #   print(f"")
        #   F, self.mutable_mapping = self.restart(chosen_swap)
        # else:
        self.mutable_mapping = chosen_mapping
        inserted_swaps.append(chosen_swap)
        final_qc.swap(chosen_swap[0], chosen_swap[1])

    return inserted_swaps, self.mutable_mapping

  def create_neighbor_table(self, graph):
    neighbor_table = np.zeros((self.num_qubits, self.num_qubits))
    edges = graph.edge_list()
    for u, v in edges:
      neighbor_table[u, v] += 1
      if u != v:
        neighbor_table[v, u] += 1
    return neighbor_table
  
  def get_F_targets(self, F):
    F_targets = set()
    for gate in F:
      for qarg in gate.qargs:
        F_targets.add(qarg.index)
    return F_targets
  
  def initialize_front_layer(self):
    front_layer = self.bidag.front_layer()
    return front_layer
  
  def can_execute_gate(self, gate):
    # logical qubits
    # print(gate.__repr__())
    if len(gate.qargs) == 1:
      return True
    else:
      # assume two-qubit gate
      q_i, q_j = gate.qargs[0].index, gate.qargs[1].index
      # print(q_i, q_j)
      Q_m, Q_n = self.mutable_mapping[q_i], self.mutable_mapping[q_j]
      # print(Q_m, Q_n)
      return self.neighbor_table[Q_m, Q_n] == 1 or self.neighbor_table[Q_n, Q_m] == 1

  def get_successors(self, gate):
    # print(gate.__repr__())
    successors = self.bidag.successors(gate)
    # for s in successors:
    #   print(s.__repr__())
    succeeding_dag_op_nodes = [s for s in successors if isinstance(s, DAGOpNode)]
    return succeeding_dag_op_nodes

  def has_resolved_dependencies(self, gate):
    # check that there is no gate in F that operates on the same qubits as those executed on by gate
    # print(gate.__repr__())

    for parent in gate.parents:
      if isinstance(parent, DAGOpNode) and parent not in self.executed_gates_set:
        return False
    return True
    
  def obtain_swaps(self, F_targets):
    # F is a list of DAGOpNodes
    # print(F_targets.__repr__())

    # Create set of size-2 tuples
    swap_candidate_set = set()

    for logical_target in F_targets:
      # assume two-qubit gate
      # print(type(logical_target))
      physical_target = self.mutable_mapping[logical_target]
      neighbors = self.find_neighbors(physical_target)
      for n in neighbors:
        swap_candidate_set.add(tuple(sorted([physical_target, n])))

    return swap_candidate_set

  def find_neighbors(self, Q_m):
    neighbors = []
    for n in np.arange(self.num_qubits):
      if self.neighbor_table[Q_m, n] == 1 or self.neighbor_table[n, Q_m] == 1:
        neighbors.append(n)
    # print(f"neighbors of {Q_m} are {neighbors}")
    return neighbors
  
  def execute_swap(self, swap, mutable_mapping):
    physical_q1, physical_q2 = swap

    logical_q1, logical_q2 = None, None
    for k, v in mutable_mapping.items():
      if v == physical_q1:
        logical_q1 = k
      if v == physical_q2:
        logical_q2 = k

    new_mapping = copy.deepcopy(mutable_mapping)
    # new_mapping = mutable_mapping.copy()
    new_mapping[logical_q1] = physical_q2
    new_mapping[logical_q2] = physical_q1
    return new_mapping

  
  def score_temp_mapping(self, swap, mutable_mapping, F):
    new_mapping = self.execute_swap(swap, mutable_mapping)
    cost = 0
    # conduct swap
    if self.heuristic == 'basic':
      cost = 0
      for gate in F:
        q_i, q_j = gate.qargs[0].index, gate.qargs[1].index
        Q_m, Q_n = new_mapping[q_i], new_mapping[q_j]
        cost += self.dist_matrix[Q_m, Q_n]

    elif self.heuristic == 'lookahead':
      pass
    elif self.heuristic == 'decay':
      pass
    else:
      print("unknown heuristic option")
    return cost, new_mapping

  


    




