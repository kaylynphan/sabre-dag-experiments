from sabre_dag_experiments.device import qcdevice
from sabre_dag_experiments.input import input_qasm
from qiskit.converters import *
from sabre_dag_experiments.qc_helpers import run_sabre, apply_layout_and_generate_sabre_swaps, construct_qc
from sabre_dag_experiments.dag_helpers import test_dagcircuit_class, run_sabre_on_dag, construct_bidirectional_dagcircuit
from qiskit.transpiler import PassManager, CouplingMap
from qiskit.transpiler.passes import SabreLayout

class Driver:
    def __init__(self, layout_trials):
        # These values should be updated in setdevice(...)
        self.device = None
        self.count_physical_qubit = 0
        self.list_qubit_edge = []
        self.swap_duration = 0
        self.dict_gate_duration = dict()
        # self.list_gate_duration = []

        # These values should be updated in setprogram(...)
        self.list_gate_qubits = []
        self.count_program_qubit = 0
        self.list_gate_name = []
        
        # bound_depth is a hyperparameter
        self.bound_depth = 0

        self.input_dependency = False
        self.list_gate_dependency = []
        self.start = 0
        self.swap_sabre = 0
        # self.ancillary_var_counter = 0

        self.layout_trials = layout_trials
 
    def set_circuit_name(self, name):
        self.circuit_name = name

    def set_device_name(self, name):
        self.device_name = name

    def setdevice(self, device: qcdevice):
        """Pass in parameters from the given device.  If in TB mode,
           swap_duration is set to 1 without modifying the device.

        Args:
            device: a qcdevice object for OLSQ
        """

        self.device = device
        self.count_physical_qubit = device.count_physical_qubit
        self.list_qubit_edge = device.list_qubit_edge
        self.swap_duration = device.swap_duration

    # Adopted from OLSQ2
    def setprogram(self, program, input_mode: str = None, gate_duration: dict = None):
        """Translate input program to OLSQ IR, and set initial depth
        An example of the intermediate representation is shown below.
        It contains three things: 1) the number of qubit in the program,
        2) a list of tuples representing qubit(s) acted on by a gate,
        the tuple has one index if it is a single-qubit gate,
        two indices if it is a two-qubit gate, and 3) a list of
        type/name of each gate, which is not important to OLSQ,
        and only needed when generating output.
        If in TB mode, initial depth=1; in normal mode, we perform ASAP
        scheduling without consideration of SWAP to calculate depth.

        Args:
            program: a qasm string, or a list of the three things in IR.
            input_mode: (optional) can be "IR" if the input has ben
                translated to OLSQ IR; can be "benchmark" to use one of
                the benchmarks.  Default mode assumes qasm input.

        Example:
            For the following circuit
                q_0: ───────────────────■───
                                        │  
                q_1: ───────■───────────┼───
                     ┌───┐┌─┴─┐┌─────┐┌─┴─┐
                q_2: ┤ H ├┤ X ├┤ TDG ├┤ X ├─
                     └───┘└───┘└─────┘└───┘ 
            count_program_qubit = 3
            gates = ((2,), (1,2), (2,), (0,1))
            gate_spec = ("h", "cx", "tdg", "cx")
        """
        
        if input_mode == "IR":
            self.count_program_qubit = program[0]
            self.list_gate_qubits = program[1]
            self.list_gate_name = program[2]
        else:
            program = input_qasm(program)
            self.count_program_qubit = program[0]
            self.list_gate_qubits = program[1]
            self.list_gate_name = program[2]

        self.dict_gate_duration = gate_duration
        # create a list to remember the gate duration. gate => duration => construct in when setting program and use for construct constraint.
        # if gate_duration != None:
        #     # self.list_gate_duration
        #     for gate_name in self.list_gate_name:
        #         self.list_gate_duration.append(self.dict_gate_duration[gate_name])
        # else:
        #     self.list_gate_duration = [1]*len(self.list_gate_qubits)

        # calculate the initial depth (Altered from OLSQ2, Removed Transition mode)
        if False: # self.mode == Mode.transition:
        # if self.if_transition_based:
            self.bound_depth = 1
        else:
            push_forward_depth = [0 for i in range(self.count_program_qubit)]
            for qubits in self.list_gate_qubits:
                if len(qubits) == 1:
                    push_forward_depth[qubits[0]] += 1
                else:
                    tmp_depth = push_forward_depth[qubits[0]]
                    if tmp_depth < push_forward_depth[qubits[1]]:
                        tmp_depth = push_forward_depth[qubits[1]]
                    push_forward_depth[qubits[1]] = tmp_depth + 1
                    push_forward_depth[qubits[0]] = tmp_depth + 1
            self.bound_depth = max(push_forward_depth)
        
        count_gate = len(self.list_gate_qubits)
        self.list_gate_two = []
        self.list_gate_single = []
        self.list_span_edge = None
        for l in range(count_gate):
            if len(self.list_gate_qubits[l]) == 1:
                self.list_gate_single.append(l)
            else:
                self.list_gate_two.append(l)
        
    def get_swap_upper_bound(self, heuristic = "sabre"):
        if heuristic == "sabre":
            swap_num, depth = run_sabre(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit)
            # print("Run heuristic compiler sabre to get upper bound for SWAP: {}, depth: {}".format(swap_num, depth))
        else:
            raise TypeError("Only support sabre.")
        return swap_num, depth
    
    def build_bidirectional_initial_mapping(self, index):
        # print("Drawing original circuit in orig_circuit.png")
        qc = construct_qc(self.list_gate_qubits, self.count_physical_qubit)
        qc.draw(scale=0.7, filename = "orig_circuit.png", output='mpl', style='color')
        device = CouplingMap(couplinglist = self.list_qubit_edge, description="sabre_test")

        # print("Drawing Coupling Map...")
        device = CouplingMap(couplinglist = self.list_qubit_edge, description="sabre_test")
        img = device.draw()
        img.save("coupling_map.png")


        # print(f"Compiling original circuit with sabre (via SabreLayout pass/PassManager) with layout_trials={self.layout_trials}...")
        sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=self.layout_trials)
        pm = PassManager(sbl)
        sabre_cir = pm.run(qc)
        # print("Drawing circuit in orig_sabre_compiled_circuit.png")
        sabre_cir.draw(scale=0.7, filename = "orig_sabre_circuit.png", output='mpl', style='color', with_layout=True)
        
        swap_count, depth = run_sabre(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, self.layout_trials)
        # print(f"Original Sabre achieves swap count: {swap_count} and depth: {depth}")

        # print(f"Running Sabre on BiDAG partitioned at index {index}...")


        ####

        bidirectional_dag = construct_bidirectional_dagcircuit(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, index)
        # print("Visualizing Reverse Circuit as Sabre will use for forward and backward pass...")
        for_cir = dag_to_circuit(bidirectional_dag)
        for_cir.draw(scale=0.7, filename = "cir_used_for_sabre_forward_pass.png", output='mpl', style='color', with_layout=True)
        rev_cir = for_cir.reverse_ops()
        rev_cir.draw(scale=0.7, filename = "cir_used_for_sabre_backward_pass.png", output='mpl', style='color', with_layout=True)

        initial_layout, out_cir, swap_num, depth = run_sabre_on_dag(bidirectional_dag, self.list_qubit_edge, self.layout_trials)

        # print(f"Drawing output of SabreLayout on BiDAG")
        out_cir.draw(scale=0.7, filename = "bidag_sabre_cir.png", output='mpl', style='color', with_layout=True)

        ###

        # dag, initial_layout = test_dagcircuit_class(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, index, self.circuit_name)

        # print("Visualizing Reverse Circuit as Sabre will use for forward and backward pass...")
        # for_cir = dag_to_circuit(dag)
        # for_cir.draw(scale=0.7, filename = "cir_used_for_sabre_forward_pass.png", output='mpl', style='color', with_layout=True)
        # rev_cir = for_cir.reverse_ops()
        # rev_cir.draw(scale=0.7, filename = "cir_used_for_sabre_backward_pass.png", output='mpl', style='color', with_layout=True)
        
        # initial_layout, swap_num, depth = run_sabre_on_dag(dag, self.list_qubit_edge, self.layout_trials)
        #

        # print(f"Swap Count when running on BiDAG: {swap_num}")

        # print(f"Verifying mapping at index {index}...")

        # print(f"Initial layout at index {index}")
        # print(initial_layout)
  
        # left_swap_count, left_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_layout, True, index, self.layout_trials)
        # print(f"Left Swap count: {left_swap_count}")
        # print(f"Left Depth: {left_depth}")

        # right_swap_count, right_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_layout, False, index, self.layout_trials)
        # print(f"Right Swap count: {right_swap_count}")
        # print(f"Right Depth: {right_depth}")

        apply_layout_and_generate_sabre_swaps(bidirectional_dag, self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_layout, True, index, self.layout_trials)

    
    def build_bidirectional_initial_mappings_for_all_indices(self):
        swap_counts = []
        depths = []
        min_indices = []
        max_indices = []
        min_swap_count = float("inf")
        max_swap_count = 0
        initial_layouts = []

        # print("Drawing original circuit in orig_circuit.png")
        qc = construct_qc(self.list_gate_qubits, self.count_physical_qubit)
        qc.draw(scale=0.7, filename = "orig_circuit.png", output='mpl', style='color')
        device = CouplingMap(couplinglist = self.list_qubit_edge, description="sabre_test")

        # print("Drawing Coupling Map...")
        device = CouplingMap(couplinglist = self.list_qubit_edge, description="sabre_test")
        img = device.draw()
        img.save("coupling_map.png")


        # print(f"Compiling original circuit with sabre (via SabreLayout pass/PassManager) with layout_trials={self.layout_trials}...")
        sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=self.layout_trials)
        pm = PassManager(sbl)
        sabre_cir = pm.run(qc)
        # print("Drawing circuit in orig_sabre_circuit.png")
        sabre_cir.draw(scale=0.7, filename = "orig_sabre_circuit.png", output='mpl', style='color', with_layout=True)
        
        swap_count, depth = run_sabre(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, self.layout_trials)
        # print(f"Sabre achieves swap count: {swap_count} and depth: {depth}")

        # print("Testing BiDAG at several indices")
        for i in range(len(self.list_gate_qubits)):
            dag, initial_layout = test_dagcircuit_class(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, i, self.circuit_name)    

            swap_num, depth = run_sabre_on_dag(dag, self.list_qubit_edge, self.layout_trials)
            if swap_num < min_swap_count:
                min_indices = [i]
                min_swap_count = swap_num
            elif swap_num == min_swap_count:
                min_indices.append(i)

            if swap_num > max_swap_count:
                max_indices = [i]
                max_swap_count = swap_num
            elif swap_num == max_swap_count:
                max_indices.append(i)
            
            print(f"Index for BiDAG: {i}, Swap Count: {swap_num}")
            swap_counts.append(swap_num)
            depths.append(depth)
            initial_layouts.append(initial_layout)

            # print(f'index: {i}, swap_count: {swap_num}, depth: {depth}')
            # print("Run heuristic compiler sabre to get upper bound for SWAP: {}, depth: {}".format(swap_num, depth))
        print(f'Zero-index partition result: swap_count: {swap_counts[0]}, depth: {depths[0]}')
        print(f'Lowest swap_count: {min_swap_count} at indices: [{str(min_indices)}]')
        print(f'Highest swap_count: {max_swap_count} at indices: [{str(max_indices)}]')

        # Each index constructs a new bidirectional dagcircuit. Each dagcircuit gets run through SABRE and returns both an initial mapping and a resulting swap count from running SABRE on the dag
        # for those indices that seem to create a minimum swap count, verify whether the mapping can be applied to the original circuit to also have an optimal result

        print("Verifying mappings that generate lowest swap count...")
        for min_index in min_indices + [0]:
            initial_layout = initial_layouts[min_index]
            print(f"Initial layout at index {min_index}")
            print(initial_layout)

            left_swap_count, left_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_layout, True, min_index, self.layout_trials)
            print(f"Left Swap count: {left_swap_count}")
            print(f"Left Depth: {left_depth}")

            right_swap_count, right_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_layout, False, min_index, self.layout_trials)
            print(f"Right Swap count: {right_swap_count}")
            print(f"Right Depth: {right_depth}")

    # QUEUE METHOD incorrectly introduces dependencies between gates from different partition
    # def run_sabre_with_dag_formation_at_all_indices(self):
    #     print("Running original sabre heuristic with layout_trials={}".format(self.layout_trials))
    #     swap_num, depth = run_sabre(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, self.layout_trials)
    #     print("Run heuristic compiler sabre to get upper bound for SWAP: {}, depth: {}".format(swap_num, depth))
        
    #     print("Indices")
    #     indices = [i for i in range(len(self.list_gate_qubits))]
    #     for i in range(len(self.list_gate_qubits)):
    #         print(str(i))
            
    #     print("Swap Counts")
    #     swap_counts = []
    #     depths = []
    #     min_indices = []
    #     max_indices = []
    #     min_swap_count = float("inf")
    #     max_swap_count = 0
    #     for i in range(len(self.list_gate_qubits)):
    #         # print("Constructing DAGCircuit at index {}".format(i))
    #         dag = construct_dagcircuit_queue_method(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, i, self.circuit_name)        
    #         swap_num, depth = run_sabre_on_dag(dag, self.list_qubit_edge, self.layout_trials)
    #         if swap_num < min_swap_count:
    #             min_indices = [i]
    #             min_swap_count = swap_num
    #         elif swap_num == min_swap_count:
    #             min_indices.append(i)

    #         if swap_num > max_swap_count:
    #             max_indices = [i]
    #             max_swap_count = swap_num
    #         elif swap_num == max_swap_count:
    #             max_indices.append(i)
            
    #         print(str(swap_num))
    #         swap_counts.append(swap_num)
    #         depths.append(depth)
    #         # print(f'index: {i}, swap_count: {swap_num}, depth: {depth}')
    #         # print("Run heuristic compiler sabre to get upper bound for SWAP: {}, depth: {}".format(swap_num, depth))
    #     print(f'Original sabre result: swap_count: {swap_counts[0]}, depth: {depths[0]}')
    #     print(f'Lowest swap_count: {min_swap_count} at indices: [{str(min_indices)}]')
    #     print(f'Highest swap_count: {max_swap_count} at indices: [{str(max_indices)}]')

    # def output_csv(self, indices, swap_counts, depths):
    #     data = list(zip(indices, swap_counts, depths))
    #     csv_file_path = 'csv_outputs/' + self.circuit_name + '_' + self.device_name

    #     # Writing to CSV file
    #     with open(csv_file_path, mode='w', newline='') as file:
    #         writer = csv.writer(file)

    #         # Write the header with additional columns
    #         header = ["index", "swap_count", "depth", "min_swap_count", "min_indices"]
    #         writer.writerow(header)

    #         # Write the data
    #         writer.writerows(data)

    #     print(f"CSV file '{csv_file_path}' has been created.")

