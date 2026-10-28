#!/usr/bin/env bash

# Simple interest calculator required for the Git/GitHub course assignment.
# Formula: Simple Interest = (Principal * Rate * Time) / 100

set -u

read -r -p "Enter principal amount: " principal
read -r -p "Enter annual rate of interest (%): " rate
read -r -p "Enter time period (years): " time

# Validate non-negative integer or decimal inputs.
number_re='^[0-9]+([.][0-9]+)?$'
if [[ ! "$principal" =~ $number_re || ! "$rate" =~ $number_re || ! "$time" =~ $number_re ]]; then
    echo "Error: Please enter valid non-negative numbers."
    exit 1
fi

interest=$(awk -v p="$principal" -v r="$rate" -v t="$time" 'BEGIN { printf "%.2f", (p * r * t) / 100 }')
echo "Simple Interest: $interest"
