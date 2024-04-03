#!/usr/bin/env bash
python3 split_by_index.py --dt grid --d 4 --f output --qf benchmark/qaoa/qaoa_16_0.qasm
python3 split_by_index.py --dt grid --d 5 --f output --qf benchmark/qaoa/qaoa_20_0.qasm
python3 split_by_index.py --dt grid --d 5 --f output --qf benchmark/qaoa/qaoa_24_0.qasm
python3 split_by_index.py --dt grid --d 6 --f output --qf benchmark/qaoa/qaoa_28_0.qasm
python3 split_by_index.py --dt grid --d 6 --f output --qf benchmark/qaoa/qaoa_36_0.qasm
python3 split_by_index.py --dt grid --d 7 --f output --qf benchmark/qaoa/qaoa_40_0.qasm
python3 split_by_index.py --dt grid --d 8 --f output --qf benchmark/qaoa/qaoa_50_0.qasm
python3 split_by_index.py --dt grid --d 8 --f output --qf benchmark/qaoa/qaoa_60_0.qasm
python3 split_by_index.py --dt grid --d 9 --f output --qf benchmark/qaoa/qaoa_80_0.qasm
