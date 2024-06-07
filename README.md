# Sabre Dag Experiments

This repository contains:
 - A BidirectionalDagCircuit class, which represents a QuantumCiruit partitioned at a certain index. The key difference between DagCircuit and BidirectionalDagCircuit is the introduction of a second output set.
 - A Python implementation of SabreSwap that operates on a Bidirectional DagCircuit.
 - A script file, split_by_index.py, which tests the effectiveness of BidagSabreSwap against Qiskit's Sabre

Workflow Details (Single Index):
1. Baseline SABRE
   - Use Qiskit's SABRE to find a baseline for swap count. Using the original SABRE algorithm means partition index = 0.
2. BiDAG Creation
3. Initial Mapping Creation:
   - Beginning with a trivial layout, perform a forward-backward iteration `layout_trials` times. Each forward-backward iteration in BiDAGSabreSwap performs a routing pass, but instead of inserting swaps, alters the original layout. Swaps can be visualized in a BiDAG after each iteration.
   - After `layout_trials` forward-backward iterations, an initial mapping is returned.
4. Initial Mapping Evaluation:
   - Using Qiskit's implementation of SabreSwap, pass in the initial mapping and perform routing. Compile the left and right partitions separately, but give both sides the same initial mapping. Add together the number of swaps inserted to get a final swap count.
  
Running the workflow without a specified index will collect BiDAGSabreSwap results from all indices.

Example execution:
```
# Runs 10 layout trials on all indices for QAOA 16, on 4x4 grid architecture.
python3 split_by_index.py --dt grid --d 4 --f example/ --qf benchmark/qaoa/qaoa_16_0.qasm --layout_trials 10

# Runs 1 layout trial on index 0 for QAOA 16, on 4x4 grid architecture.
python3 split_by_index.py --dt grid --d 4 --f output --qf benchmark/qaoa/qaoa_16_0.qasm --layout_trials 1 --index 0        
```
