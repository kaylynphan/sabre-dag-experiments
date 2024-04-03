from sabre_dag_experiments.device import qcdevice
from sabre_dag_experiments.input import input_qasm
from qiskit.converters import *
from sabre_dag_experiments.qc_helpers import run_sabre, apply_layout_and_generate_sabre_swaps, construct_qc
from sabre_dag_experiments.dag_helpers import test_bidagcircuit_class, run_sabre_on_dag, construct_bidirectional_dagcircuit, construct_reverse_bidirectional_dagcircuit
from qiskit.transpiler import PassManager, CouplingMap
from qiskit.transpiler.passes import SabreLayout
from qiskit.circuit import Qubit, QuantumRegister
from sabre_dag_experiments.bidag_sabre_swap import BiDAGSabreSwap

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
            swap_num, depth = run_sabre(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, self.layout_trials)
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

        bidirectional_dag = construct_bidirectional_dagcircuit(self.list_gate_qubits, self.count_physical_qubit, index)
        reverse_bidirectional_dag = construct_reverse_bidirectional_dagcircuit(bidirectional_dag, self.count_physical_qubit, index)

        initial_mapping =  {
            k: k for k in range(self.count_physical_qubit)
        }

        for _ in range(self.layout_trials):
            for dir in ["forward", "reverse"]:
                if dir == 'forward':
                    dag = bidirectional_dag
                else:
                    dag = reverse_bidirectional_dag
                sbs = BiDAGSabreSwap(bidag=dag, coupling_map=device, initial_mapping=initial_mapping, heuristic="basic", seed=None, trials=None)
                swaps, final_mapping = sbs.run()

                initial_mapping = final_mapping
        
        final_swap_count = swaps
    
        print(f"SabreLayout with {self.layout_trials} layout trials found this initial mapping and swap count:")
        print(initial_mapping)
        print(final_swap_count)
        
        left_swap_count, left_depth = apply_layout_and_generate_sabre_swaps(bidirectional_dag, self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_mapping, True, index, self.layout_trials)

    def build_bidirectional_initial_mappings_for_all_indices(self):
        qc = construct_qc(self.list_gate_qubits, self.count_physical_qubit)
        qc.draw(scale=0.7, filename = "orig_circuit.png", output='mpl', style='color')
        device = CouplingMap(couplinglist = self.list_qubit_edge, description="sabre_test")

        # print("Drawing Coupling Map...")
        device = CouplingMap(couplinglist = self.list_qubit_edge, description="sabre_test")
        img = device.draw()
        img.save("coupling_map.png")

        results = []
        for index in range(len(self.list_gate_qubits)):
            bidirectional_dag = construct_bidirectional_dagcircuit(self.list_gate_qubits, self.count_physical_qubit, index)
            reverse_bidirectional_dag = construct_reverse_bidirectional_dagcircuit(bidirectional_dag, self.count_physical_qubit, index)
            initial_mapping =  {
                k: k for k in range(self.count_physical_qubit)
            }

            for _ in range(self.layout_trials):
                for dir in ["forward", "reverse"]:
                    if dir == 'forward':
                        dag = bidirectional_dag
                    else:
                        dag = reverse_bidirectional_dag
                    sbs = BiDAGSabreSwap(bidag=dag, coupling_map=device, initial_mapping=initial_mapping, heuristic="basic", seed=None, trials=None)
                    swaps, final_mapping = sbs.run()

                    initial_mapping = final_mapping
            
            final_swap_count = swaps
        
            print(f"SabreLayout with {self.layout_trials} layout trials found this initial mapping and swap count:")
            print(initial_mapping)
            print(final_swap_count)

            # convert initial_mapping from int->int dict to int->Qubit dict
            initial_mapping = {k: Qubit(register=QuantumRegister(size=self.count_physical_qubit, name='q'), index=v) for k, v in initial_mapping.items()}
            
            left_swap_count, left_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_mapping, True, index, self.layout_trials)
            right_swap_count, right_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_mapping, False, index, self.layout_trials)

            results.append({'index': index, 'swap_count': left_swap_count + right_swap_count, 'depth': left_depth + right_depth})
        return results








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


        sbl = SabreLayout(coupling_map = device, seed = 0, layout_trials=self.layout_trials)
        pm = PassManager(sbl)
        sabre_cir = pm.run(qc)
        # print("Drawing circuit in orig_sabre_circuit.png")
        sabre_cir.draw(scale=0.7, filename = "orig_sabre_circuit.png", output='mpl', style='color', with_layout=True)
        
        swap_count, depth = run_sabre(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, self.layout_trials)
        # print(f"Sabre achieves swap count: {swap_count} and depth: {depth}")

        # print("Testing BiDAG at several indices")


        results = []

        for i in range(len(self.list_gate_qubits)):
            for _ in range(self.layout_trials):
                for dir in ["forward", "reverse"]:
                    if dir == 'forward':
                        dag = bidirectional_dag
                    else:
                        dag = reverse_bidirectional_dag
                    sbs = BiDAGSabreSwap(bidag=dag, coupling_map=device, initial_mapping=initial_mapping, heuristic="basic", seed=None, trials=None)
                    swaps, final_mapping = sbs.run()

                    initial_mapping = final_mapping
            
            final_swap_count = swaps
            print(f"Index: {i}")
            dag = test_bidagcircuit_class(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, i, self.circuit_name)
            initial_layout, sabre_cir, swap_num, depth = run_sabre_on_dag(dag, self.list_qubit_edge, self.layout_trials)
            print(f"Swap count on sabre-compiled bidag: {swap_num}")
            print(f"Depth: {depth}")

            left_swap_count, left_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_layout, True, i, self.layout_trials)
            print(f"Left Swap count: {left_swap_count}")
            print(f"Left Depth: {left_depth}")

            right_swap_count, right_depth = apply_layout_and_generate_sabre_swaps(self.list_gate_qubits, self.list_qubit_edge, self.count_physical_qubit, initial_layout, False, i, self.layout_trials)
            print(f"Right Swap count: {right_swap_count}")
            print(f"Right Depth: {right_depth}")

            print(f"Total swaps: {left_swap_count + right_swap_count}")
            print(f"Total depth: {left_depth + right_depth}")
            results.append({'index': i, 'swap_count': left_swap_count + right_swap_count, 'depth': left_depth + right_depth})

        return results