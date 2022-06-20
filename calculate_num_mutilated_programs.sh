#!/usr/bin/env bash
#Title			: calculate_num_mutilated_programs.sh
#Usage			: bash calculate_num_mutilated_programs.sh
#Author			: pmorvalho
#Date			: June 15, 2022
#Description    	: Prints the number of mutilated programs generated using each type of program mutilation 
#Notes			: 
# (C) Copyright 2022 Pedro Orvalho.
#==============================================================================

mutilations=("wrong_comp_ops" "variable_misuse" "assignment_deletion" "all")
mutilations_flags=("-c"  "-vm" "-ad" "-a")

if [[ $1 == "" ]]; then
    dataset="C-Pack-IPAs"
    labs=("lab02" "lab03" "lab04") 	# we are not considering lab05 for this dataset, and only year 2020/2021 has lab05.
else
    labs=("lab3" "lab4" "lab5" "lab6")
    dataset="itsp"
fi

years=()

for y in $(find $dataset/correct_submissions/* -maxdepth 0 -type d);
do
    y=$(echo $y | rev | cut -d '/' -f 1 | rev)
    years+=("$y")
    echo "Found year: "$y
done

# data_dir="/data/benchmarks/mutilated_programs"
data_dir="mutilated_programs"

mkdir -p results_csvs/mutilations
output_file="results_csvs/mutilations/"$dataset"-number_mutilated_programs.txt"
echo "" > $output_file
# echo "" > results_csvs/mutilations/$dataset-summary.txt

mutilate_ex_programs(){
    local ex_dir=$1
    local out_dir=$2
    local info=$3
    local year=$4
    local lab=$5
    local ex=$6
    local n_mut=0
    local num_mut_progs_ex=0
    local n_mutilations=0
    echo "Mutating "$ex_dir
    for((m1=0;m1<${#mutilations[@]};m1++));
    do
	local mut1=${mutilations[$m1]}
	local f1=${mutilations_flags[$m1]}
	# echo $mut1
	local n_mutilations=$(python prog_mutilator.py -d $ex_dir -o $out_dir/$mut1 $f1 -info)
	echo $info/$mut1","$n_mutilations  | tee -a $output_file | tee -a results_csvs/mutilations/$dataset-$year-$lab.txt | tee -a results_csvs/mutilations/$dataset-$year.txt
	local n_mutilations=$((n_mutilations))
	num_mut_progs_ex=$((num_mut_progs_ex+n_mutilations))
	n_mut=$((n_mut+1))
    done
    echo
    echo "Total "$info": "$num_mut_progs_ex | tee -a $output_file | tee -a results_csvs/mutilations/$dataset-$year-$lab.txt | tee -a results_csvs/mutilations/$dataset-$year.txt
}

mutilate_lab_programs(){
    local lab_dir=$1
    local year=$2
    local lab=$3
    local sub_type=$4
    for ex in $(find $lab_dir/ex* -maxdepth 0 -type d);
    do
	ex=$(echo $ex | rev | cut -d '/' -f 1 | rev)
	mkdir -p  $data_dir/$sub_type/$year/$lab/$ex
	mutilate_ex_programs  $lab_dir/$ex $data_dir/$sub_type/$year/$lab/$ex $year/$lab/$ex $year $lab $ex &
    done
    wait
}

mutilate_programs(){
# $1 - year directory
# $2 - submissions directory
    local year=$1
    local sub_dir=$2
    local sub_type=$(echo $sub_dir | rev | cut -d '/' -f 1 | rev)
    # local total_number_mutilated_progs=0
    for((l=0;l<${#labs[@]};l++));
    do
	lab=${labs[$l]}
	echo "" > results_csvs/mutilations/$dataset-$year-$lab.txt
	mutilate_lab_programs $sub_dir/$year/$lab $year $lab $sub_type  &
    done
    wait
}

echo "Starting program mutation..."
for((y=0;y<${#years[@]};y++));
do
    ys=${years[$y]}
    echo "" > results_csvs/mutilations/$dataset-$ys.txt
    mutilate_programs $ys $dataset/correct_submissions &
done
