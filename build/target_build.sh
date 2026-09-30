#!/bin/bash

# This script builds and installs, on the Jetson itself (stock Jetpack 7.2.1):
# out-of-tree kernel modules & device tree overlays
#
# Usage: source target_build.sh, then run one of the printed commands.


# color output
red=$'\e[31m'
grn=$'\e[32m'
yel=$'\e[33m'
blu=$'\e[34m'
mag=$'\e[35m'
cyn=$'\e[36m'
normal=$'\e[0m'


# export env
_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export L4T_SOURCE=${L4T_SOURCE:-$(cd "${_script_dir}/../source" && pwd)}
export KERNEL_RELEASE=${KERNEL_RELEASE:-$(uname -r)}


# check kernel headers and build tools
function _preflight() {
    if [ "${KERNEL_RELEASE}" != "$(uname -r)" ]; then
        echo -e "${red}modules would be built for ${KERNEL_RELEASE} but the running kernel is $(uname -r)${normal}"
        return 1
    fi
    if [ ! -d "/lib/modules/${KERNEL_RELEASE}/build" ]; then
        echo -e "${red}kernel headers /lib/modules/${KERNEL_RELEASE}/build not found; install nvidia-l4t-kernel-headers${normal}"
        return 1
    fi
    local tool
    for tool in make gcc cpp dtc; do
        if ! command -v ${tool} &> /dev/null; then
            echo -e "${red}${tool} not found; install build-essential and device-tree-compiler${normal}"
            return 1
        fi
    done
}

# Errors are passed on with "|| return 1" rather than "set -e": bash ignores
# set -e inside functions called from "&&", "||" or "if", as in
# "check && install_all".

# build out-of-tree kernel modules
function build_oot_modules() {
    _preflight || return 1
    echo ; echo; echo -e "${yel}start out of tree kernel modules build ... ${normal}"
    make -C ${L4T_SOURCE} modules KERNEL_HEADERS=/lib/modules/${KERNEL_RELEASE}/build || return 1
}

# build FRAMOS device tree overlays
function build_dtree() {(
    set -o pipefail
    overlay_dir=${L4T_SOURCE}/hardware/nvidia/t23x/nv-public/overlay
    out_dir=${L4T_SOURCE}/out/dtbo
    inc=""
    for dir in ${L4T_SOURCE}/hardware/nvidia/*/nv-public/include/*; do
        [ -d "${dir}" ] && inc="${inc} -I ${dir}"
    done
    echo ; echo; echo -e "${yel}start device tree overlays build ... ${normal}"
    mkdir -p ${out_dir} || exit 1
    for dts in ${overlay_dir}/*fr_*-overlay.dts; do
        name=$(basename ${dts} .dts)
        if ! cpp -nostdinc -undef -x assembler-with-cpp -D__DTS__ ${inc} ${dts} \
                | dtc -@ -q -I dts -O dtb -o ${out_dir}/${name}.dtbo -; then
            echo -e "${red}overlay ${name} failed to build${normal}"
            exit 1
        fi
    done
    echo -e "${grn}$(ls ${out_dir}/*.dtbo | wc -l) overlays in ${out_dir}${normal}"
)}

# build DTBs & out-of-tree kernel modules
function build_all() {
    build_dtree || return 1
    build_oot_modules || return 1
}

# check the build environment and build everything without installing
function check() {
    _preflight || return 1
    build_all || return 1
    echo
    echo -e "${grn}$(find ${L4T_SOURCE}/nvidia-oot -name '*.ko' | wc -l) modules" \
        "($(find ${L4T_SOURCE}/nvidia-oot -name 'fr_*.ko' | wc -l) fr_*)," \
        "$(ls ${L4T_SOURCE}/out/dtbo/*.dtbo | wc -l) overlays${normal}"
}


echo; echo; echo -e "${grn}L4T_SOURCE = ${L4T_SOURCE}"
echo -e "${grn}KERNEL_RELEASE = ${KERNEL_RELEASE}"


echo; echo "${cyn}C O M M A N D S:"
echo -e "${red}build_dtree${normal}:	\t\tbuild device tree overlays"
echo -e "${red}build_oot_modules${normal}:\t\tbuild out-of-tree kernel modules"
echo -e "${red}build_all${normal}:	\t\tbuild all"
echo -e "${red}check${normal}:	\t\t\tcheck the build environment and build all without installing"

echo
