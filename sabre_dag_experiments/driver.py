from sabre_dag_experiments.device import qcdevice
from sabre_dag_experiments.input import input_qasm
from sabre_dag_experiments.run_h_compiler import run_sabre, run_sabre_on_dag, apply_layout_and_generate_sabre_swaps
from sabre_dag_experiments.sabre_dag_circuit import construct_dagcircuit3, test_dagcircuit_class
import csv


class Driver:
    def __init__(self, obj_is_swap, mode, encoding, swap_up_bound = -1, layout_trials=1):
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
        self.card_encoding = encoding
        self.swap_up_bound = swap_up_bound
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

        # calculate the initial depth
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

    def setdependency(self, dependency: list):
        """Specify dependency (non-commutation)

        Args:
            dependency: a list of gate index pairs
        
        Example:
            For the following circuit
                q_0: ───────────────────■───
                                        │  
                q_1: ───────■───────────┼───
                     ┌───┐┌─┴─┐┌─────┐┌─┴─┐
                q_2: ┤ H ├┤ X ├┤ TDG ├┤ X ├─
                     └───┘└───┘└─────┘└───┘ 
                gate   0    1     2     3
            dependency = [(0,1), (1,2), (2,3)]

            However, for this QAOA subcircuit (ZZ gates may have phase
            parameters, but we neglect them for simplicity here)
                         ┌──┐ ┌──┐
                q_0: ────┤ZZ├─┤  ├─
                     ┌──┐└┬─┘ │ZZ│  
                q_1: ┤  ├─┼───┤  ├─
                     │ZZ│┌┴─┐ └──┘
                q_2: ┤  ├┤ZZ├──────
                     └──┘└──┘ 
                gate   0   1   2
            dependency = []    # since ZZ gates are commutable
        """
        self.list_gate_dependency = dependency
        self.input_dependency = True
        
    
    def get_swap_upper_bound(self, heuristic = "sabre"):
        if heuristic == "sabre":
            swap_num, depth = run_sabre(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit)
            print("Run heuristic compiler sabre to get upper bound for SWAP: {}, depth: {}".format(swap_num, depth))
        else:
            raise TypeError("Only support sabre.")
        return swap_num, depth
    
    def build_bidirectional_initial_mappings(self):
        swap_counts = []
        depths = []
        min_indices = []
        max_indices = []
        min_swap_count = float("inf")
        max_swap_count = 0
        initial_layouts = []

        for i in range(len(self.list_gate_qubits)):
            print("Index: {}".format(i))
            dag, initial_layout = test_dagcircuit_class(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, i, self.circuit_name)    

            swap_num, depth = run_sabre_on_dag(dag, self.list_qubit_edge, False, self.layout_trials)
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
            
            print(f"swap count derived by running sabre on bidirectional dagcircuit: {swap_num}")
            swap_counts.append(swap_num)
            depths.append(depth)
            initial_layouts.append(initial_layout)

            # print(f'index: {i}, swap_count: {swap_num}, depth: {depth}')
            # print("Run heuristic compiler sabre to get upper bound for SWAP: {}, depth: {}".format(swap_num, depth))
        print(f'Original sabre result: swap_count: {swap_counts[0]}, depth: {depths[0]}')
        print(f'Lowest swap_count: {min_swap_count} at indices: [{str(min_indices)}]')
        print(f'Highest swap_count: {max_swap_count} at indices: [{str(max_indices)}]')

        # Each index constructs a new bidirectional dagcircuit. Each dagcircuit gets run through SABRE and returns both an initial mapping and a resulting swap count from running SABRE on the dag
        # for those indices that seem to create a minimum swap count, verify whether the mapping can be applied to the original circuit to also have an optimal result

        print("Verifying mappings that generate lowest swap count...")
        for min_index in min_indices:
            initial_layout = initial_layouts[min_index]
            print(f"Initial layout at index {min_index}")
            print(initial_layout)
            left_swap_count, left_depth = apply_layout_and_generate_sabre_swaps(reversed(self.list_gate_qubits[:min_index]), self.list_qubit_edge, self.count_physical_qubit, initial_layout, True)
            print(f"Left Swap count: {left_swap_count}")
            print(f"Left Depth: {left_depth}")

            right_swap_count, right_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits[min_index:], self.list_qubit_edge, self.count_physical_qubit, initial_layout, False)
            print(f"Right Swap count: {right_swap_count}")
            print(f"Right Depth: {right_depth}")

    
    def run_sabre_with_dag_formation_at_all_indices(self):
        print("Running original sabre heuristic with layout_trials={}".format(self.layout_trials))
        swap_num, depth = run_sabre(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, self.layout_trials)
        print("Run heuristic compiler sabre to get upper bound for SWAP: {}, depth: {}".format(swap_num, depth))
        
        print("Indices")
        indices = [i for i in range(len(self.list_gate_qubits))]
        for i in range(len(self.list_gate_qubits)):
            print(str(i))
            
        print("Swap Counts")
        swap_counts = []
        depths = []
        min_indices = []
        max_indices = []
        min_swap_count = float("inf")
        max_swap_count = 0
        for i in range(len(self.list_gate_qubits)):
            # print("Constructing DAGCircuit at index {}".format(i))
            dag = construct_dagcircuit3(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, i, self.circuit_name)        
            swap_num, depth = run_sabre_on_dag(dag, self.list_qubit_edge, False, self.layout_trials)
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
            
            print(str(swap_num))
            swap_counts.append(swap_num)
            depths.append(depth)
            # print(f'index: {i}, swap_count: {swap_num}, depth: {depth}')
            # print("Run heuristic compiler sabre to get upper bound for SWAP: {}, depth: {}".format(swap_num, depth))
        print(f'Original sabre result: swap_count: {swap_counts[0]}, depth: {depths[0]}')
        print(f'Lowest swap_count: {min_swap_count} at indices: [{str(min_indices)}]')
        print(f'Highest swap_count: {max_swap_count} at indices: [{str(max_indices)}]')

    def output_csv(self, indices, swap_counts, depths):
        data = list(zip(indices, swap_counts, depths))
        csv_file_path = 'csv_outputs/' + self.circuit_name + '_' + self.device_name

        # Writing to CSV file
        with open(csv_file_path, mode='w', newline='') as file:
            writer = csv.writer(file)

            # Write the header with additional columns
            header = ["index", "swap_count", "depth", "min_swap_count", "min_indices"]
            writer.writerow(header)

            # Write the data
            writer.writerows(data)

        print(f"CSV file '{csv_file_path}' has been created.")

