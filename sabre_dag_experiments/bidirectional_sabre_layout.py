import copy 
from qiskit.circuit.quantumregister import QuantumRegister, Qubit
from qiskit._accelerate.nlayout import NLayout, SabreDAG


def sabre_layout_and_routing(
    bidirectional_dagcircuit,
    neighbor_table,
    distance_matrix,
    heuristic,
    max_iterations,
    num_swap_trials,
    num_random_trials
    seed,
    partial_layouts):

  starting_layouts = [[] for _ in range(num_random_trials)]
  if partial_layouts:
    starting_layouts = partial_layouts
  dist = list(distance_matrix)


def layout_trial(
    dag,
    neighbor_table,
    distance_matrix,
    heuristic,
    seed,
    max_iterations,
    num_swap_trials,
    run_swap_in_parallel,
    starting_layout):
    num_physical_qubits = distance_matrix.size()
    rng = seed(seed)

    if starting_layout: # is not empty
      used_bits = set([copy(b) for b in starting_layout])
      free_bits = [n for n in range(num_physical_qubits) if n not in used_bits]
      free_bits.shuffle(rng)

      def get_assigned_qubit(x):
        phys = starting_layout.index(x) if x in starting_layout else free_bits.pop()
        return Qubit(QuantumRegister(num_physical_qubits, 'q'), phys)
        
      physical_qubits = [get_assigned_qubit(n) for n in range(num_physical_qubits)]
    else:
      physical_qubits = [Qubit(QuantumRegister(num_physical_qubits, 'q'), i) for i in range(num_physical_qubits)]
      physical_qubits.shuffle(rng)
    
    initial_layout = NLayout.from_virtual_to_physical(physical_qubits)
    
    dag_no_control_forward = SabreDAG(
        dag.num_qubits,
        dag.num_clbits,
        dag.dag.clone(),
        dag.nodes.clone(),
        dag.first_layer.clone(),
        {index: [] for index in dag.node_blocks.keys()}
    )

    dag_no_control_reverse = SabreDAG(
        dag_no_control_forward.num_qubits,
        dag_no_control_forward.num_clbits,
        copy.deepcopy(dag_no_control_forward.nodes)
        copy.deepcopy(dag_no_control_forward.node_blocks)
    )

    def build_swap_map_inner(
          num_qubits,
          dag,
          neighbor_table,
          dist,
          heuristic,
          seed,
          initial_layout,
          num_trials,
          run_in_parallel
    ):
        # if not run_in_parallel:
        #    run_in_parallel = getenv_use_multiple_threads() && num_trials > 1
       coupling_graph = neighbor_table.coupling_graph()
       outer_rng = Seed(seed) if seed else from_entropy()

       seed_cev = outer_rng.sample_iter()
       
       


    for _ in range(max_iterations):
        for dag in [dag_no_control_forward, dag_no_control_reverse]:
            result, final_layout = build_swap_map_inner(
                num_physical_qubits,
                dag,
                neighbor_table,
                distance_matrix,
                heuristic,
                seed,
                initial_layout,
                1,
                False
            )
            initial_layout = final_layout
    
    result, final_layout = build_swap_map_inner(
        num_physical_qubits,
        dag,
        neighbor_table,
        distance_matrix,
        heuristic,
        seed,
        initial_layout,
        1,
        False
    )
    final_permutation = [virt.to_phys(final_layout) for (_, virt) in initial_layout]
    
    


    
