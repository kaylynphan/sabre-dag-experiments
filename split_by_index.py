import argparse
import json
from sabre_dag_experiments.device import qcdevice
from sabre_dag_experiments.driver import Driver
from device_creation import get_nnGrid, get_device_by_name
'''
    How to run:
    python3 split_by_index.py --dt grid --d 4 --f example/ --qf benchmark/qaoa/qaoa_16_0.qasm --layout_trials 1
'''

def build_bidirectional_initial_mappings_for_all_indices(circuit_info, circuit_name, device_name, device, layout_trials):
    lsqc_solver = Driver(layout_trials)
    lsqc_solver.set_circuit_name(circuit_name)
    lsqc_solver.set_device_name(device_name)
    lsqc_solver.setprogram(circuit_info)
    lsqc_solver.setdevice(device)
    return lsqc_solver.build_bidirectional_initial_mappings_for_all_indices()

def run_basic_sabre(circuit_info, device, layout_trials):
    lsqc_solver = Driver(layout_trials)
    lsqc_solver.setprogram(circuit_info)
    lsqc_solver.setdevice(device)
    return lsqc_solver.get_swap_upper_bound(heuristic="basic")

def build_bidirectional_initial_mapping(circuit_info, circuit_name, device_name, device, layout_trials, index, initial_layout):
    lsqc_solver = Driver(layout_trials)
    lsqc_solver.set_circuit_name(circuit_name)
    lsqc_solver.set_device_name(device_name)
    lsqc_solver.setprogram(circuit_info)
    lsqc_solver.setdevice(device)
    return lsqc_solver.build_bidirectional_initial_mapping(index, initial_layout)

if __name__ == "__main__":
    # Initialize parser
    parser = argparse.ArgumentParser()
    # Adding optional argument
    parser.add_argument("--dt", dest='device_type', type=str,
        help="grid, ourense, sycamore, rochester, tokyo, aspen-4, or eagle")
    parser.add_argument("--d", dest='device', type=int,
        help="device (x-by-x grid)")
    parser.add_argument("--f", dest='folder', type=str, default='.',
        help="the folder to store results")
    parser.add_argument("--qf", dest="qasm", type=str,
        help="Input file name")
    parser.add_argument("--encoding", dest="encoding", type=int, default=1,
        help="seqcounter = 1, sortnetwrk  = 2, cardnetwrk  = 3, totalizer   = 6, mtotalizer  = 7. kmtotalizer = 8, native = 9")
    parser.add_argument("--sabre", action='store_true', default=False,
        help="Use sabre to get SWAP upper bound")
    parser.add_argument("--tran", action='store_true', default=False,
        help="Use TB-OLSQ")
    parser.add_argument("--swap", action='store_true', default=False,
        help="Optimize SWAP")
    parser.add_argument("--swap_bound", dest="swap_bound", type=int, default=-1,
        help="user define swap bound")
    parser.add_argument("--swap_duration", dest="swap_duration", type=int, default=1,
        help="swap duration")
    parser.add_argument("--layout_trials", dest="layout_trials", type=int, default=1,
        help="sabre layout trials")
    parser.add_argument("--index", dest="index", default=-1, type=int,
        help="sabre layout trials")
    # Read arguments from command line
    
    args = parser.parse_args()
    circuit_name = args.qasm
    circuit_info = open(args.qasm, "r").read()
    if args.device_type == "grid":
        device = get_nnGrid(args.device, args.swap_duration)
        device_name = str(args.device) + 'x'+ str(args.device) + "grid"
    else:
        device = get_device_by_name(args.device_type, args.swap_duration)
        device_name = args.device_type

    data = dict()
    b_file = args.qasm.split('.')
    b_file = b_file[-2]
    b_file = b_file.split('/')
    b_file = b_file[-1]

    if args.index == -1:
        file_name = args.folder+"/"+str(args.device_type)+"_"+b_file+"_trials_"+str(args.layout_trials)+".json"
    else:
        file_name = args.folder+"/"+str(args.device_type)+"_"+b_file+"_trials_"+str(args.layout_trials)+"_index_"+str(args.index)+".json"

    # layout_trials = args.layout_trials
# print(f"layout_trials is {layout_trials}")

    basic_sabre_swap_count, depth, initial_layout = run_basic_sabre(circuit_info, device, args.layout_trials)

    if args.index == -1:
        result = build_bidirectional_initial_mappings_for_all_indices(circuit_info, circuit_name, device_name, device, args.layout_trials)
    else:
        result = build_bidirectional_initial_mapping(circuit_info, circuit_name, device_name, device, args.layout_trials, args.index, initial_layout)

    data["device"] = str(args.device)
    data["circuit"] = circuit_name
    data["layout_trials"] = args.layout_trials
    data["basic_sabre"] = {'swap_count': basic_sabre_swap_count, 'depth': depth}
    data["result"] = result
    
    if args.index == -1:
        lowest_swap = highest_swap = result[0]["swap_count"]
        lowest_layout_swap_count = result[0]["layout_swap_count"]
        lowest_idx = highest_idx = 0
        lowest_layout_swap_count_idx = 0
        for i in range(1, len(result)):
            if result[i]["swap_count"] > highest_swap:
                highest_swap = result[i]["swap_count"]
                highest_idx = i
            if result[i]["swap_count"] < lowest_swap:
                lowest_swap = result[i]["swap_count"]
                lowest_idx = i
            if result[i]["layout_swap_count"] < lowest_layout_swap_count:
                lowest_layout_swap_count = result[i]["swap_count"]
                lowest_layout_swap_count_idx = i
        data["lowest_result"] = result[lowest_idx]
        data["highest_result"] = result[highest_idx]
        data["lowest_layout_swap_count_result"] = result[lowest_layout_swap_count_idx]

    with open(file_name, 'w') as file_object:
        json.dump(data, file_object, default=int)
