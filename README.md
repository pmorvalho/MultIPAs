# MultIPAS

MultIPAs : Applying Program Transformations to Introductory Programming Assignments for Data Augmentation

MultIPAs is a program transformation framework capable of augmenting small imperative C program benchmarks by performing six different syntactic program mutations and three semantic program mutilations.
MultIPAs keeps the information about the types and the number of bugs present in each incorrect program generated, which can be used to train ML-based program repair frameworks. Furthermore, MultIPAs produces a variable mapping between the original program given as input and the mutated/mutilated program.

MultIPAs is divided into two modules: Program Mutator and Program Mutilator.

[Demonstration Video](https://arsr.inesc-id.pt/~pmorvalho/MultIPAs-demo.html).

## Program Mutator

The following six syntactic program mutations are available on MultIPAs' program mutator:

+ _M1 - Comparison Expression Mirroring (CEM)_: MultIPAs mirrors one or several comparison expressions e.g. $a \ge b$ becomes $b \le a$;
+ _M2 - If-else-statements Swapping (IES)_: MultIPAs swaps the if-branch and the else-branch and negates the if-condition. This is done only for simple if-else-statements, i.e., there are no more if-statements inside the else-branch;
+ _M3 - Increment/Decrement Operators Mirroring (IOM)_: MultIPAs mirrors the two increment (and decrement) operators in the C programming language (e.g. **c++** and **++c**), only when the return value of the expression that contains the increment/decrement operator is discarded e.g. the increment step of a for-loop;
+ _M4 - Variable Declarations Reordering (VDR)_: MultIPAs reorders the variables' declarations present in each code block. For this, our framework takes into account the dependencies between the variables' declarations i.g if a variable declaration depends on other variables, this is done by computing all possible topological orders of the variables' declarations;
+ _M5 - For-2-While Translation (F2W)_: MultIPAs translates for-loops into while-loops. Just in cases of for-loops that do not contain any continue instructions;
+ _M6 - Variable Addition (VA)_: MultIPAs introduces a new dummy variable declaration in the program. The mutated program does not have the same set of variables as the original program.

### Usage:

```
usage: prog_mutator.py [-h] [-c] [-if] [-io] [-dv] [-rd] [-fw] [-a] [-p PERCENTAGE_TOTAL_PROGS] [-info] [-ea] [-v] -d INPUT_DIR -o OUTPUT_DIR 

optional arguments:
  -h, --help            show this help message and exit
  -c, --comp_ops        Swaps the comparison operators.
  -if, --if_else        Swaps the simple if-else-statements.
  -io, --incr_ops       Swaps the increment operators (e.g. i++, ++i and i+=1) if these are not used in a binary operation or in an assignment.
  -dv, --dummy_var      Declares a dummy variable in the beginning of the main function.
  -rd, --reord_decls    Reorder the order of variable declarations, when it is possible i.e., when two variables' declarations do not depend on each other
  -fw, --for_2_while    Translates simple for-loops (without any continue instruction) into a while-loop.
  -a, --all_mut         Performs all the mutations above.
  -p PERCENTAGE_TOTAL_PROGS, --percentage_total_progs PERCENTAGE_TOTAL_PROGS
                        Instead of generating all possible mutations the script only generates this percentage. Default 0.01 if the total number of possible mutations is higher than 100k or 0.1 otherwise.
  -d INPUT_DIR, --input_dir INPUT_DIR
                        Name of the input directory.
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        Name of the output directory.
  -info, --info         Prints the total number of programs the required mutations can produced and exits without producing the sets of programs.
  -ea, --enumerate_all  Enumerates all possible mutated programs. NOTE: Sometimes the number of mutated programs is more than 200K Millions of programs.
  -v, --verbose         Prints debugging information.
```

## Program Mutilator

The following three semantic program mutilations are available on MultIPAs' program mutilator:

+ _B1 - Wrong Comparison Operator (WCO)_: MultIPAs swaps an expression's comparison operators for some syntactically similar operator e.g. swaps the operator **<** for **<=**. MultIPAs can also swap **>** for **>=**, **<=** for **<**, **>=** for **>**, **==** for **=**, and **!=** for **==**;
+ _B2 - Variable Misuse (VM)_: MultIPAs swaps a variable in the program by another variable of the same type. The resulting mutilated program can be compiled successfully since MultIPAS ensures that both variables are of the same type;
+ _B3 - Assignment Deletion (AD)_: MultIPAs deletes an assignment expression in the program.


```
usage: prog_mutilator.py [-h] [-c] [-vm] [-ad] [-a] [-s] [-n NUM_MUT] [-pp NUM_PROGS_2_PROCESS] [-info] [-v] -d INPUT_DIR -o OUTPUT_DIR 

optional arguments:
  -h, --help            show this help message and exit
  -c, --comp_ops        Swaps the comparison operators.
  -vm, --var_mu         Introduces a bug of variable misuse.
  -ad, --asg_del        Introduces a bug of expression deletion (assignments).
  -a, --all_mut         Performs all the mutilations above.
  -s, --single          Generates a single erroneous programs, instead of enumerating all possibilities.
  -n NUM_MUT, --num_mut NUM_MUT
                        Number of mutilations to be performed. (Default = 1).
  -pp NUM_PROGS_2_PROCESS, --num_progs_2_process NUM_PROGS_2_PROCESS
                        Number of programs to process from the input directory. (Default = 50).
  -info, --info         Prints the total number of programs the required mutilations can produced and exits without producing the sets of programs.
  -d INPUT_DIR, --input_dir INPUT_DIR
                        Name of the input directory.
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        Name of the output directory.
  -v, --verbose         Prints debugging information.
```


## Variable Mapping

Every time MultIPAs mutates or mutilates a program, a mapping between the original program's set of variables and the mutated/mutilated program's sets of variables is generated. This variable mapping can help program repair frameworks that rely on mappings between the sets of variables of the correct implementation and the incorrect program they are trying to repair.

## References

P. Orvalho, M. Janota, and V. Manquinho. MultIPAs: Applying Program Transformations to Introductory Programming Assignments for Data Augmentation. In 30th ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering, ESEC/FSE 2022. [https://dl.acm.org/doi/10.1145/3540250.3558931](https://dl.acm.org/doi/10.1145/3540250.3558931).

## Introductory Programming Assignments (IPAs) Datasets 

+ [ITSP](https://github.com/pmorvalho/MultIPAs/tree/main/itsp/correct_submissions/year-1) : [https://github.com/jyi/ITSP](https://github.com/jyi/ITSP);
    - Reference: Jooyong Yi, Umair Z. Ahmed, Amey Karkare, Shin Hwei Tan, and Abhik Roychoudhury. A feasibility study of using automated program repair for introductory programming assignments. ESEC/FSE 2017. [http://jooyongyi.com/papers/Yi-ESEC-FSE17.pdf](http://jooyongyi.com/papers/Yi-ESEC-FSE17.pdf).
+ [C-Pack-IPAs](https://github.com/pmorvalho/C-Pack-IPAs) : [https://github.com/pmorvalho/C-Pack-IPAs](https://github.com/pmorvalho/C-Pack-IPAs);
    - Reference: Pedro Orvalho, Mikoláš Janota, and Vasco Manquinho. C-Pack of IPAs: A C90 Program Benchmark of Introductory Programming Assignments. 2022. [https://arxiv.org/pdf/2206.08768.pdf](https://arxiv.org/pdf/2206.08768.pdf) 

## Installation Requirements

+ Python 3.8.5
+ [pycparser](https://github.com/eliben/pycparser) : version 2.21
  ```
  pip install pycparser==2.21
  ```
+ numpy : version 1.19.2
  ```
  pip install numpy==1.19.2
  ```
