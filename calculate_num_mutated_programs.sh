#!/usr/bin/env bash
#Title			: calculate_num_mutated_programs.sh
#Usage			: bash calculate_num_mutated_programs.sh
#Author			: pmorvalho
#Date	 		: May 27, 2022
#Description    	: Prints the number of mutated programs generated using each type of program mutation
#Notes			: 
# (C) Copyright 2022 Pedro Orvalho.
#==============================================================================

mutations=("swap_comp_ops" "swap_if_else_sttms" "swap_incr_decr_ops" "decl_dummy_vars" "reorder_decls" "for_2_while" "all")
mutations_flags=("-c"  "-if" "-io" "-dv" "-rd" "-fw" "-a")
# mutations=("swap_comp_ops")
# mutations_flags=("-c")

if [[ $1 == "" ]]; then
    dataset="C-Pack-IPAs"
    labs=("lab02" "lab03" "lab04")      # we are not considering lab05 for this dataset, and only year 2020/2021 has lab05.
else
    labs=("lab3" "lab4" "lab5" "lab6")
    dataset="itsp"
fi

years=()

# mutations=("swap_if_else_sttms" "decl_dummy_vars")
# mutations_flags=("-if" "-dv")
# labs=("lab02")

for y in $(find $dataset/correct_submissions/* -maxdepth 0 -type d);
do
    y=$(echo $y | rev | cut -d '/' -f 1 | rev)
    years+=("$y")
    echo "Found year: "$y
done

# data_dir="/data/benchmarks/mutated_programs"
data_dir="mutated_programs"

mkdir results_csvs
output_file="results_csvs/"$dataset"-number_mutated_programs.txt"
echo "" > $output_file
# echo "" > results_csvs/$dataset-summary.txt

print_info(){
  # $1 - directory with the set of students' directoris mutated
  # $2 - shorten name to use for csv file
  local mut_dir=$1
  local mut_name=$2
  local mutated_progs=$((-1)) 	# -1 to not consider the original program
  for d in $(find $mut_dir/* -maxdepth 0 -type d);
  do
      for f in $(find $d/*.c -maxdepth 0 -type f);
      do
	  local mutated_progs=$((mutated_progs+1))
      done
  done
  echo $mut_name","$mutated_progs >> $output_file
  rm $mut_dir/*/var_*
  tar zcf $mut_dir.tar.gz $mut_dir  >> tar_log.log
  rm -rf $mut_dir
  echo $mutated_progs 
}

mutate_ex_programs(){
    local ex_dir=$1
    local out_dir=$2
    local info=$3
    local year=$4
    local lab=$5
    local ex=$6
    local n_mut=0
    local num_mut_progs_ex=0
    local n_mutations=0
    echo "Mutating "$ex_dir
    for((m1=0;m1<${#mutations[@]};m1++));
    do
	local mut1=${mutations[$m1]}
	local f1=${mutations_flags[$m1]}
	# echo $mut1
	local n_mutations=$(python prog_mutator.py -d $ex_dir -o $out_dir/$mut1 $f1 -ea -info)
	echo $info/$mut1","$n_mutations  | tee -a $output_file | tee -a results_csvs/$dataset-$year-$lab.txt | tee -a results_csvs/$dataset-$year.txt
	# local n_mutations=$(print_info $out_dir/$mut1 $info/$mut1)
	local n_mutations=$((n_mutations))
	num_mut_progs_ex=$((num_mut_progs_ex+n_mutations))
	n_mut=$((n_mut+1))
	# for((m2=m1+1;m2<${#mutations[@]};m2++));
	# do
	#     local mut2=${mutations[$m2]}
	#     local f2=${mutations_flags[$m2]}
	#     # echo $mut1-$mut2
	#     local n_mutations=$(python prog_mutator.py -d $ex_dir -o $out_dir/$mut1-$mut2 $f1 $f2 -ea -info)
	#     echo $info/$mut1-$mut2","$n_mutations >> $output_file
	#     # local n_mutations=$(print_info $out_dir/$mut1-$mut2 $info/$mut1-$mut2)
	#     local n_mutations=$((n_mutations))
	#     num_mut_progs_ex=$((num_mut_progs_ex+n_mutations))
 	#     n_mut=$((n_mut+1))
	#     for((m3=m2+1;m3<${#mutations[@]};m3++));
	#     do
	# 	local mut3=${mutations[$m3]}
	# 	local f3=${mutations_flags[$m3]}
	# 	# echo $mut1-$mut2-$mut3
	# 	local n_mutations=$(python prog_mutator.py -d $ex_dir -o $out_dir/$mut1-$mut2-$mut3 $f1 $f2 $f3 -ea -info)
	# 	echo $info/$mut1-$mut2-$mut3","$n_mutations >> $output_file
	# 	#local n_mutations=$(print_info $out_dir/$mut1-$mut2-$mut3 $info/$mut1-$mut2-$mut3)
	# 	local n_mutations=$((n_mutations))
	#         num_mut_progs_ex=$((num_mut_progs_ex+n_mutations))
	# 	n_mut=$((n_mut+1))
	# 	for((m4=m3+1;m4<${#mutations[@]};m4++));
	# 	do
	# 	    local mut4=${mutations[$m4]}
	# 	    local f4=${mutations_flags[$m4]}
	# 	    # echo $mut1-$mut2-$mut3-$mut4
	# 	    local n_mutations=$(python prog_mutator.py -d $ex_dir -o $out_dir/$mut1-$mut2-$mut3-$mut4 $f1 $f2 $f3 $f4 -ea -info)
	# 	    echo $info/$mut1-$mut2-$mut3$mut4","$n_mutations >> $output_file
	# 	    # local n_mutations=$(print_info $out_dir/$mut1-$mut2-$mut3-$mut4 $info/$mut1-$mut2-$mut3-$mut4)
	# 	    local n_mutations=$((n_mutations))
	# 	    num_mut_progs_ex=$((num_mut_progs_ex+n_mutations))
	# 	    n_mut=$((n_mut+1))
	# 	    for((m5=m4+1;m5<${#mutations[@]};m5++));
	# 	    do
	# 		local mut5=${mutations[$m5]}
	# 		local f5=${mutations_flags[$m5]}
	# 		# echo $mut1-$mut2-$mut3-$mut4-$mut5
	# 		local n_mutations=$(python prog_mutator.py -d $ex_dir -o $out_dir/$mut1-$mut2-$mut3-$mut4-$mut5 $f1 $f2 $f3 $f4 $f5 -ea -info)
	# 		echo $info/$mut1-$mut2-$mut3$mut4-$mut5","$n_mutations >> $output_file
	# 		# local n_mutations=$(print_info  $data_dir/$sub_type/$year/$lab/$ex/$mut1-$mut2-$mut3-$mut4-$mut5 $info/$mut1-$mut2-$mut3-$mut4-$mut5)
	# 		local n_mutations=$((n_mutations))
	#                 num_mut_progs_ex=$((num_mut_progs_ex+n_mutations))
	# 		n_mut=$((n_mut+1))
	# 		for((m6=m5+1;m6<${#mutations[@]};m6++));
	# 		do
	# 		    local mut6=${mutations[$m6]}
	# 		    local f6=${mutations_flags[$m6]}
	# 		    # echo $mut1-$mut2-$mut3-$mut4-$mut5
	# 		    local n_mutations=$(python prog_mutator.py -d $ex_dir -o $out_dir/$mut1-$mut2-$mut3-$mut4-$mut5-$mut6 $f1 $f2 $f3 $f4 $f5 $f6 -ea -info)
	# 		    echo $info/$mut1-$mut2-$mut3$mut4-$mut5-$mut6","$n_mutations >> $output_file
	# 		    # local n_mutations=$(print_info $out_dir/$mut1-$mut2-$mut3-$mut4-$mut5-$mut6 $info/$mut1-$mut2-$mut3-$mut4-$mut5-$mut6)
	# 		    local n_mutations=$((n_mutations))
	#                     num_mut_progs_ex=$((num_mut_progs_ex+n_mutations))
	# 		    n_mut=$((n_mut+1))
	# 		done
	# 	    done
	# 	done
	#     done
	# done
    done
    echo
    echo "Total "$info": "$num_mut_progs_ex | tee -a $output_file | tee -a results_csvs/$dataset-$year-$lab.txt | tee -a results_csvs/$dataset-$year.txt
}

mutate_lab_programs(){
    local lab_dir=$1
    local year=$2
    local lab=$3
    local sub_type=$4
    for ex in $(find $lab_dir/ex* -maxdepth 0 -type d);
    do
	ex=$(echo $ex | rev | cut -d '/' -f 1 | rev)
	mkdir -p  $data_dir/$sub_type/$year/$lab/$ex
	mutate_ex_programs  $lab_dir/$ex $data_dir/$sub_type/$year/$lab/$ex $year/$lab/$ex $year $lab $ex &
    done
    wait
}

mutate_programs(){
# $1 - year directory
# $2 - submissions directory
    local year=$1
    local sub_dir=$2
    local sub_type=$(echo $sub_dir | rev | cut -d '/' -f 1 | rev)
    # local total_number_mutated_progs=0
    for((l=0;l<${#labs[@]};l++));
    do
	lab=${labs[$l]}
	echo "" > results_csvs/$dataset-$year-$lab.txt
	mutate_lab_programs $sub_dir/$year/$lab $year $lab $sub_type  &
    done
    wait
}

echo "Starting program mutation..."
for((y=0;y<${#years[@]};y++));
do
    ys=${years[$y]}
    echo "" > results_csvs/$dataset-$ys.txt
    mutate_programs $ys $dataset/correct_submissions &
done
